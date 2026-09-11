"""在 Blender 中生成无品牌包装示例，无需外部图片或模型素材。"""
import argparse
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
root = Path(args.output).resolve()
root.mkdir(parents=True, exist_ok=True)
if (root / 'demo.blend').exists():
    parser.error('demo.blend already exists; choose a new output directory.')
bpy.ops.wm.read_factory_settings(use_empty=True)

def material(name, color, roughness=.3, metallic=0):
    """设置基础颜色、粗糙度和金属感，供各个包装部件复用。"""
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    shader = result.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return result

cream = material('Porcelain cream', (.72, .64, .49), .35)
teal = material('Deep petrol', (.012, .075, .085), .28)
gold = material('Brushed brass', (.45, .25, .065), .28, .7)
floor = material('Slate', (.028, .048, .059), .45)
parts = []

def cylinder(name, radius, depth, z, mat):
    """用圆柱构建容器部件，倒角让边缘在灯光下更自然。"""
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=radius, depth=depth, location=(0, 0, z))
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    bevel = ob.modifiers.new('Edge softness', 'BEVEL')
    bevel.width = .035
    bevel.segments = 4
    for poly in ob.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    parts.append(ob)
    return ob

cylinder('Container', .73, 1.8, .94, cream)
cylinder('Wrap band', .738, 1.02, .95, teal)
cylinder('Top brass band', .75, .025, 1.45, gold)
cylinder('Bottom brass band', .75, .025, .44, gold)
cylinder('Lid', .76, .19, 1.94, teal)
cylinder('Lid detail', .67, .015, 2.045, gold)
# 用简单圆环装饰标签区域；示例不使用真实商标。
bpy.ops.mesh.primitive_torus_add(major_segments=64, minor_segments=12, location=(0, -.746, 1.03), rotation=(math.pi/2, 0, 0), major_radius=.16, minor_radius=.012)
emblem = bpy.context.object
emblem.name = 'Geometric emblem'
emblem.data.materials.append(gold)
parts.append(emblem)
# 所有产品部件挂到同一个空物体上，通过它统一控制转台动画。
rig = bpy.data.objects.new('Turntable', None)
bpy.context.collection.objects.link(rig)
for ob in parts:
    ob.parent = rig
rig.rotation_euler[2] = -.25
rig.keyframe_insert('rotation_euler', frame=1)
rig.rotation_euler[2] = .25
rig.keyframe_insert('rotation_euler', frame=48)

# 大平面接住阴影，三盏面光分别补充主体亮度、侧面和轮廓。
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.data.materials.append(floor)
def aim(ob, point):
    ob.rotation_euler = (Vector(point) - ob.location).to_track_quat('-Z', 'Y').to_euler()
for loc, power, size in [((-3, -4, 5), 650, 4), ((3, -1, 3), 400, 3), ((1, 3, 4), 850, 3)]:
    bpy.ops.object.light_add(type='AREA', location=loc)
    lamp = bpy.context.object
    lamp.data.energy = power
    lamp.data.shape = 'DISK'
    lamp.data.size = size
    aim(lamp, (0, 0, 1))
# 正交相机减少透视变化，让示例侧重包装比例与材质。
bpy.ops.object.camera_add(location=(3, -8, 4))
camera = bpy.context.object
aim(camera, (0, 0, 1.05))
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 4.0
scene = bpy.context.scene
scene.camera = camera
scene.world = bpy.data.worlds.new('World')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.12, .17, .2, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .35
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1200
scene.render.resolution_y = 750
scene.render.resolution_percentage = 100
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 48
scene.frame_set(24)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(root / 'demo.png')
# 保存可编辑工程，再渲染当前帧；后续可用 render_frames.py 输出动画帧。
bpy.ops.wm.save_as_mainfile(filepath=str(root / 'demo.blend'))
bpy.ops.render.render(write_still=True)
print('DEMO_COMPLETE', root)
