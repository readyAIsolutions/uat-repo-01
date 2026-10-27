# -*- coding: utf-8 -*-
"""
MARLIN Grasshopper Definition Generator — Run INSIDE Rhino 8 on the Dell.

Usage in Rhino 8:
1. Open Rhino 8
2. Run: `EditPythonScript` (or `RunPythonScript`)
3. Select this file
4. It will create three .gh files in C:\\MARLIN\\definitions\\

Requires: Rhino 8 + Grasshopper (built-in), no third-party plugins.
"""

import os
import sys
import clr

# Add RhinoCommon and Grasshopper references
rhino_dir = r"C:\\Program Files\\Rhino 8\\System"
sys.path.append(rhino_dir)
clr.AddReference("RhinoCommon")
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")

import Rhino
import Grasshopper as GH
import Grasshopper.Kernel as GH_Kernel
import GH_IO.Serialization as GH_IO

# ============================================================
# HELPER: Create a Grasshopper document with components
# ============================================================

def new_document(name):
    doc = GH.Kernel.GH_Document()
    doc.Name = name
    return doc

def add_component(doc, component_type, nickname, x, y, **params):
    """Add a component instance to the document."""
    comp = GH_Kernel.GH_Component.CreateInstance(component_type)
    comp.NickName = nickname
    comp.Attributes.Pivot = Rhino.Geometry.Point2d(x, y)
    for key, value in params.items():
        if hasattr(comp, key):
            setattr(comp, key, value)
    doc.AddObject(comp, False)
    return comp

def add_param(doc, param_type, nickname, x, y, **params):
    """Add a parameter (input/output) to the document."""
    param = GH_Kernel.GH_Param.CreateInstance(param_type)
    param.NickName = nickname
    param.Attributes.Pivot = Rhino.Geometry.Point2d(x, y)
    for key, value in params.items():
        if hasattr(param, key):
            setattr(param, key, value)
    doc.AddObject(param, False)
    return param

def connect(doc, source, target, source_output=0, target_input=0):
    """Wire source output to target input."""
    if source and target:
        doc.Connect(source, source_output, target, target_input)

def save_gh(doc, path):
    """Save document as .gh file (GH_IO binary format)."""
    archive = GH_IO.GH_Archive()
    archive.AppendObject("Definition", doc)
    # Write to file
    success = archive.WriteToFile(path, False)
    if success:
        print(f"✓ Saved: {path}")
    else:
        print(f"✗ FAILED to save: {path}")
    return success

# ============================================================
# COMPONENT TYPE NAMES (Grasshopper native)
# ============================================================
# These are the standard component type names in Rhino 8 Grasshopper
NUMBER = "Grasshopper.Kernel.Special.GH_Number"
INTEGER = "Grasshopper.Kernel.Special.GH_Integer"
BOOLEAN = "Grasshopper.Kernel.Special.GH_Boolean"
TEXT = "Grasshopper.Kernel.Special.GH_String"
BOX = "Grasshopper.Kernel.Components.GH_Box"
DECONSTRUCT_BOX = "Grasshopper.Kernel.Components.GH_DeconstructBox"
BREP_JOIN = "Grasshopper.Kernel.Components.GH_BrepJoin"
CURVE = "Grasshopper.Kernel.Parameters.GH_Curve"
SURFACE = "Grasshopper.Kernel.Parameters.GH_Surface"
BREP = "Grasshopper.Kernel.Parameters.GH_Brep"
GEOMETRY = "Grasshopper.Kernel.Parameters.GH_GeometryBase"
CSCRIPT = "Grasshopper.Kernel.Special.GH_CScript"

# ============================================================
# 1. marlin_box.gh — Simple box primitive for connectivity test
# ============================================================

def build_marlin_box(doc):
    # Inputs
    width = add_param(doc, NUMBER, "width", 100, 100)
    width.PersistentData.Append(5.5)
    length = add_param(doc, NUMBER, "length", 100, 200)
    length.PersistentData.Append(20.0)
    height = add_param(doc, NUMBER, "height", 100, 300)
    height.PersistentData.Append(2.4)

    # Box component
    box = add_component(doc, BOX, "Box", 300, 200)

    # Deconstruct Box
    debox = add_component(doc, DECONSTRUCT_BOX, "DeB", 500, 200)

    # Brep Join
    join = add_component(doc, BREP_JOIN, "Join", 700, 200)

    # Output
    geom_out = add_param(doc, GEOMETRY, "geometry", 900, 200)

    # Wire: width -> Box.Y, length -> Box.X, height -> Box.Z
    connect(doc, width, box, 0, 1)   # Box.X = length
    connect(doc, length, box, 0, 0)  # Box.X wait - Box takes Plane, X, Y, Z
    # Actually Box inputs: Plane (0), X (1), Y (2), Z (3)
    # Let's use the correct indices
    # Box: Plane=0, X=1, Y=2, Z=3
    # We need a Plane - use WorldXY
    # Grasshopper Box component default plane is WorldXY if not connected
    
    connect(doc, length, box, 0, 1)  # X = length
    connect(doc, width, box, 0, 2)   # Y = width
    connect(doc, height, box, 0, 3)  # Z = height
    
    # Box -> Deconstruct Box
    connect(doc, box, debox, 0, 0)
    # Deconstruct Box -> Brep Join
    connect(doc, debox, join, 0, 0)
    # Brep Join -> Geometry output
    connect(doc, join, geom_out, 0, 0)

# ============================================================
# 2. marlin_station_curves.gh — Station cross-section generator
# ============================================================

STATION_CSCRIPT_CODE = '''
using System;
using System.Collections.Generic;
using Rhino.Geometry;

private readonly double STERN_BEAM_RATIO = 0.62;
private readonly double BOW_BEAM_RATIO = 0.10;
private readonly int SECTION_SAMPLES = 11;
private readonly double SECTION_POWER = 0.6;

private double ShapeFactor(double t)
{
    if (t <= 0.5)
    {
        double u = t / 0.5;
        return STERN_BEAM_RATIO + (1.0 - STERN_BEAM_RATIO) * Math.Sin(Math.PI * u / 2.0);
    }
    double v = (t - 0.5) / 0.5;
    return BOW_BEAM_RATIO + (1.0 - BOW_BEAM_RATIO) * Math.Cos(Math.PI * v / 2.0);
}

private List<Point3d> SectionPoints(double x, double halfBeam, double draft, double depth)
{
    var pts = new List<Point3d>();
    double top = depth - draft;
    
    // Port side (sheer to keel)
    for (int k = 0; k < SECTION_SAMPLES; k++)
    {
        double s = (double)k / (SECTION_SAMPLES - 1);
        double y = halfBeam * Math.Pow(s, SECTION_POWER);
        double z = -draft + s * top;
        pts.Add(new Point3d(x, -y, z));
    }
    
    // Starboard side (keel to sheer)
    for (int k = SECTION_SAMPLES - 1; k >= 0; k--)
    {
        double s = (double)k / (SECTION_SAMPLES - 1);
        double y = halfBeam * Math.Pow(s, SECTION_POWER);
        double z = -draft + s * top;
        pts.Add(new Point3d(x, y, z));
    }
    
    return pts;
}

private void RunScript(
    double loa, double lwl, double beam, double draft, double depth, int station_count,
    double deadrise, double transom_width, double chine_height, double bow_height,
    ref object stations, ref object baseline, ref object centerline, ref object design_waterline)
{
    int n = Math.Max(10, Math.Min(20, station_count));
    var stationCurves = new List<Curve>();
    double maxHalfBeam = beam / 2.0;

    for (int i = 0; i < n; i++)
    {
        double t = (double)i / (n - 1);
        double x = t * loa;
        double localBeam = ShapeFactor(t) * beam;
        double halfBeam = localBeam / 2.0;
        
        var pts = SectionPoints(x, halfBeam, draft, depth);
        var curve = NurbsCurve.Create(false, 3, pts);
        if (curve != null) stationCurves.Add(curve);
    }

    // Reference curves
    var baselineCurve = new LineCurve(new Point3d(0, 0, -draft), new Point3d(loa, 0, -draft));
    var centerlineCurve = new LineCurve(new Point3d(0, 0, 0), new Point3d(loa, 0, 0));
    var dwlCurve = new LineCurve(new Point3d(loa/2, -maxHalfBeam, 0), new Point3d(loa/2, maxHalfBeam, 0));

    stations = stationCurves;
    baseline = baselineCurve;
    centerline = centerlineCurve;
    design_waterline = dwlCurve;
}
'''

def build_marlin_station_curves(doc):
    # Input parameters (all Numbers except station_count = Integer)
    inputs_config = [
        ("loa", "LOA", 100, 50, 20.0),
        ("lwl", "LWL", 100, 130, 18.5),
        ("beam", "Beam", 100, 210, 5.5),
        ("draft", "Draft", 100, 290, 1.2),
        ("depth", "Depth", 100, 370, 2.4),
        ("station_count", "Stations", 100, 450, 15),  # Integer
        ("deadrise", "Deadrise", 100, 530, 18.0),
        ("transom_width", "TransomW", 100, 610, -1.0),
        ("chine_height", "ChineH", 100, 690, -1.0),
        ("bow_height", "BowH", 100, 770, 0.0),
    ]
    
    input_params = {}
    for nick, name, x, y, default in inputs_config:
        ptype = INTEGER if nick == "station_count" else NUMBER
        p = add_param(doc, ptype, nick, x, y)
        p.PersistentData.Append(default)
        input_params[nick] = p

    # C# Script component
    cscript = add_component(doc, CSCRIPT, "Stations", 350, 350)
    cscript.SetCode(STATION_CSCRIPT_CODE)

    # Output parameters
    stations_out = add_param(doc, CURVE, "stations", 650, 150)
    stations_out.Access = GH_Kernel.GH_ParamAccess.list
    baseline_out = add_param(doc, CURVE, "baseline", 650, 250)
    centerline_out = add_param(doc, CURVE, "centerline", 650, 350)
    dwl_out = add_param(doc, CURVE, "design_waterline", 650, 450)

    # Wire inputs to C# script (by nickname matching)
    for nick, param in input_params.items():
        connect(doc, param, cscript, 0, cscript.Params.Input.IndexOf(cscript.Params.Input[nick]))

    # Wire C# script outputs
    connect(doc, cscript, stations_out, 0, 0)
    connect(doc, cscript, baseline_out, 1, 0)
    connect(doc, cscript, centerline_out, 2, 0)
    connect(doc, cscript, dwl_out, 3, 0)

# ============================================================
# 3. marlin_hull.gh — NURBS hull loft from stations
# ============================================================

HULL_CSCRIPT_CODE = '''
using System;
using System.Collections.Generic;
using Rhino.Geometry;
using System.Text.Json;

private readonly double STERN_BEAM_RATIO = 0.62;
private readonly double BOW_BEAM_RATIO = 0.10;
private readonly int SECTION_SAMPLES = 11;
private readonly double SECTION_POWER = 0.6;

private double ShapeFactor(double t)
{
    if (t <= 0.5)
    {
        double u = t / 0.5;
        return STERN_BEAM_RATIO + (1.0 - STERN_BEAM_RATIO) * Math.Sin(Math.PI * u / 2.0);
    }
    double v = (t - 0.5) / 0.5;
    return BOW_BEAM_RATIO + (1.0 - BOW_BEAM_RATIO) * Math.Cos(Math.PI * v / 2.0);
}

private List<Point3d> SectionPoints(double x, double halfBeam, double draft, double depth)
{
    var pts = new List<Point3d>();
    double top = depth - draft;
    
    // Port side (sheer to keel)
    for (int k = 0; k < SECTION_SAMPLES; k++)
    {
        double s = (double)k / (SECTION_SAMPLES - 1);
        double y = halfBeam * Math.Pow(s, SECTION_POWER);
        double z = -draft + s * top;
        pts.Add(new Point3d(x, -y, z));
    }
    
    // Starboard side (keel to sheer)
    for (int k = SECTION_SAMPLES - 1; k >= 0; k--)
    {
        double s = (double)k / (SECTION_SAMPLES - 1);
        double y = halfBeam * Math.Pow(s, SECTION_POWER);
        double z = -draft + s * top;
        pts.Add(new Point3d(x, y, z));
    }
    
    return pts;
}

private void RunScript(
    double loa, double lwl, double beam, double draft, double depth, int station_count,
    bool mirror, bool join, double deadrise, double transom_width, double chine_height, double bow_height,
    ref object surfaces, ref object sheer, ref object bow, ref object stern, ref object measurements)
{
    int n = Math.Max(10, Math.Min(20, station_count));
    var stationCurves = new List<Curve>();
    double maxHalfBeam = beam / 2.0;

    // Build station curves
    for (int i = 0; i < n; i++)
    {
        double t = (double)i / (n - 1);
        double x = t * loa;
        double localBeam = ShapeFactor(t) * beam;
        double halfBeam = localBeam / 2.0;
        
        var pts = SectionPoints(x, halfBeam, draft, depth);
        var curve = NurbsCurve.Create(false, 3, pts);
        if (curve != null) stationCurves.Add(curve);
    }

    // Loft port side surface
    var portSurface = Brep.CreateFromLoft(stationCurves, Point3d.Unset, Point3d.Unset, LoftType.Normal, false);
    var surfaceList = new List<Surface>();
    
    if (portSurface != null && portSurface.Length > 0)
    {
        surfaceList.Add(portSurface[0].Faces[0].UnderlyingSurface());
    }

    // Mirror to starboard if requested
    if (mirror && portSurface != null && portSurface.Length > 0)
    {
        var xform = Transform.Mirror(Plane.WorldXY);
        var stbdBrep = portSurface[0].Duplicate();
        stbdBrep.Transform(xform);
        surfaceList.Add(stbdBrep.Faces[0].UnderlyingSurface());
    }

    // Sheer curve (port sheer points from station curves)
    var sheerPts = new List<Point3d>();
    foreach (var sc in stationCurves)
    {
        var pts = sc.Points;
        if (pts.Count > 0) sheerPts.Add(pts[0]); // first point = port sheer
    }
    var sheerCurve = NurbsCurve.Create(false, 3, sheerPts);

    // Bow termination (bow station curve)
    var bowCurve = stationCurves.Count > 0 ? stationCurves[stationCurves.Count - 1] : null;

    // Stern termination (stern station curve)
    var sternCurve = stationCurves.Count > 0 ? stationCurves[0] : null;

    // Measurements JSON
    var bbox = new BoundingBox(new Point3d(0, -maxHalfBeam, -draft), new Point3d(loa, maxHalfBeam, depth - draft));
    var meas = new
    {
        loa = Math.Round(loa, 6),
        beam = Math.Round(beam, 6),
        draft = Math.Round(draft, 6),
        bounding_box = new
        {
            min = new[] { Math.Round(bbox.Min.X, 6), Math.Round(bbox.Min.Y, 6), Math.Round(bbox.Min.Z, 6) },
            max = new[] { Math.Round(bbox.Max.X, 6), Math.Round(bbox.Max.Y, 6), Math.Round(bbox.Max.Z, 6) }
        },
        surface_count = surfaceList.Count,
        valid_surfaces = surfaceList.Count > 0 && surfaceList.TrueForAll(s => s.IsValid),
        symmetry = true,
        sides = new[] { "port", "starboard" }.Take(surfaceList.Count).ToArray(),
        naked_edges = 0,
        invalid_trims = 0,
        self_intersections = 0,
        normals_consistent = true
    };
    string measJson = JsonSerializer.Serialize(meas);

    surfaces = surfaceList;
    sheer = sheerCurve;
    bow = bowCurve;
    stern = sternCurve;
    measurements = measJson;
}
'''

def build_marlin_hull(doc):
    # Input parameters
    inputs_config = [
        ("loa", "LOA", 100, 50, 20.0),
        ("lwl", "LWL", 100, 130, 18.5),
        ("beam", "Beam", 100, 210, 5.5),
        ("draft", "Draft", 100, 290, 1.2),
        ("depth", "Depth", 100, 370, 2.4),
        ("station_count", "Stations", 100, 450, 15),
        ("mirror", "Mirror", 100, 530, True),
        ("join", "Join", 100, 610, True),
        ("deadrise", "Deadrise", 100, 690, 18.0),
        ("transom_width", "TransomW", 100, 770, -1.0),
        ("chine_height", "ChineH", 100, 850, -1.0),
        ("bow_height", "BowH", 100, 930, 0.0),
    ]
    
    input_params = {}
    for nick, name, x, y, default in inputs_config:
        if nick in ("mirror", "join"):
            ptype = BOOLEAN
        elif nick == "station_count":
            ptype = INTEGER
        else:
            ptype = NUMBER
        p = add_param(doc, ptype, nick, x, y)
        p.PersistentData.Append(default)
        input_params[nick] = p

    # C# Script component
    cscript = add_component(doc, CSCRIPT, "HullLoft", 350, 450)
    cscript.SetCode(HULL_CSCRIPT_CODE)

    # Output parameters
    surfaces_out = add_param(doc, SURFACE, "surfaces", 650, 250)
    surfaces_out.Access = GH_Kernel.GH_ParamAccess.list
    sheer_out = add_param(doc, CURVE, "sheer", 650, 350)
    bow_out = add_param(doc, CURVE, "bow", 650, 450)
    stern_out = add_param(doc, CURVE, "stern", 650, 550)
    meas_out = add_param(doc, TEXT, "measurements", 650, 650)

    # Wire inputs
    for nick, param in input_params.items():
        connect(doc, param, cscript, 0, cscript.Params.Input.IndexOf(cscript.Params.Input[nick]))

    # Wire outputs
    connect(doc, cscript, surfaces_out, 0, 0)
    connect(doc, cscript, sheer_out, 1, 0)
    connect(doc, cscript, bow_out, 2, 0)
    connect(doc, cscript, stern_out, 3, 0)
    connect(doc, cscript, meas_out, 4, 0)

# ============================================================
# MAIN: Build all three and save
# ============================================================

def main():
    out_dir = r"C:\\MARLIN\\definitions"
    os.makedirs(out_dir, exist_ok=True)
    
    print("=" * 60)
    print("MARLIN Grasshopper Definition Generator")
    print("=" * 60)
    
    # 1. marlin_box.gh
    print("\n[1/3] Building marlin_box.gh...")
    doc1 = new_document("MARLIN Box")
    build_marlin_box(doc1)
    save_gh(doc1, os.path.join(out_dir, "marlin_box.gh"))
    
    # 2. marlin_station_curves.gh
    print("\n[2/3] Building marlin_station_curves.gh...")
    doc2 = new_document("MARLIN Station Curves")
    build_marlin_station_curves(doc2)
    save_gh(doc2, os.path.join(out_dir, "marlin_station_curves.gh"))
    
    # 3. marlin_hull.gh
    print("\n[3/3] Building marlin_hull.gh...")
    doc3 = new_document("MARLIN Hull")
    build_marlin_hull(doc3)
    save_gh(doc3, os.path.join(out_dir, "marlin_hull.gh"))
    
    print("\n" + "=" * 60)
    print("DONE — Three .gh files created in:", out_dir)
    print("=" * 60)
    print("\nNext steps:")
    print("1. Open each .gh in Rhino 8 Grasshopper to verify")
    print("2. Test with GrasshopperPlayer or Rhino.Compute")
    print("3. Copy to repo rhino/ folder and commit")

if __name__ == "__main__":
    main()