"""在 Blender 内运行：--python render_frames.py -- --scene file.blend --output dir。

保留原始工程，通过工程指纹与参数清单判断能否续渲染。
每帧先写临时文件，成功后再改名，避免把未完成的图片当作成品。
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--samples', type=int, default=48)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--start', type=int)
    parser.add_argument('--end', type=int)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if min(args.width, args.height, args.samples, args.threads) < 1:
        parser.error('Dimensions, samples and threads must be positive.')
    source = Path(args.scene).resolve()
    output = Path(args.output).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    if scene.render.engine != 'CYCLES':
        parser.error('This helper expects a Cycles scene; save the intended engine first.')
    if any(image.source == 'FILE' and not image.packed_file for image in bpy.data.images):
        parser.error('Pack file-based images before rendering so resume detects asset changes.')
    if any(mod.type in {'MESH_CACHE', 'MESH_SEQUENCE_CACHE'} for ob in scene.objects for mod in ob.modifiers):
        parser.error('External geometry caches need project-specific rendering, not this helper.')
    start = scene.frame_start if args.start is None else args.start
    end = scene.frame_end if args.end is None else args.end
    if start > end:
        parser.error('Start frame must not exceed end frame.')
    # 工程、Blender 版本或脚本发生变化时，要求使用新目录，防止混入旧帧。
    manifest = {
        'scene': str(source),
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'blender': bpy.app.version_string,
        'width': args.width, 'height': args.height,
        'samples': args.samples, 'threads': args.threads,
        'start': start, 'end': end,
        'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / 'render_manifest.json'
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding='utf-8')) != manifest:
            parser.error('Scene/settings changed. Use a new output directory.')
    elif any(output.iterdir()):
        parser.error('Output is not empty and has no matching manifest. Use a new directory.')
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # 只修改内存中的渲染设置，不覆盖用户提供的 .blend 文件。
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.cycles.samples = args.samples
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = args.threads
    scene.render.image_settings.file_format = 'PNG'
    scene.render.use_sequencer = False
    scene.render.use_persistent_data = True
    started = time.monotonic()
    rendered = skipped = 0
    for frame in range(start, end + 1):
        target = output / f'frame_{frame:04d}.png'
        if target.exists():
            # 实际读取图片并核对尺寸，不能仅凭文件名判断已经完成。
            image = bpy.data.images.load(str(target), check_existing=False)
            valid = tuple(image.size) == (args.width, args.height)
            bpy.data.images.remove(image)
            if not valid:
                raise RuntimeError(f'Unexpected existing frame dimensions: {target}')
            skipped += 1
            continue
        # 渲染中断时只留下临时文件，下次运行会重新生成这一帧。
        temporary = output / f'frame_{frame:04d}.partial.png'
        scene.frame_set(frame)
        scene.render.filepath = str(temporary)
        bpy.ops.render.render(write_still=True)
        temporary.replace(target)
        rendered += 1
        progress = {'frame': frame, 'end': end, 'rendered': rendered,
                    'skipped': skipped, 'seconds': round(time.monotonic() - started, 1)}
        (output / 'progress.json').write_text(json.dumps(progress), encoding='utf-8')
        print(json.dumps(progress), flush=True)
    print(f'RENDER_COMPLETE rendered={rendered} skipped={skipped}', flush=True)


if __name__ == '__main__':
    main()
