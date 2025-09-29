# core/batch_worker.py
import concurrent.futures
import pathlib
from core.exporter import compose_watermark_on_image

def ensure_output_path(src_path, out_dir, prefix='', suffix='', keep_name=True):
    src = pathlib.Path(src_path)
    if keep_name:
        name = src.stem
    else:
        name = src.stem
    new_name = f"{prefix}{name}{suffix}{src.suffix}"
    dst = pathlib.Path(out_dir) / new_name
    # 如果文件存在，追加序号
    i = 1
    while dst.exists():
        dst = pathlib.Path(out_dir) / f"{prefix}{name}{suffix}_{i}{src.suffix}"
        i += 1
    return str(dst)

def batch_export(tasks, max_workers=2, progress_callback=None):
    """
    tasks: list of dicts, 每个 dict 包含 src_path, dst_path, watermark_img(pil), anchor, output_format, jpeg_quality, resize_to
    progress_callback(idx, total, success, message)
    """
    results = []
    total = len(tasks)
    def worker(task):
        try:
            compose_watermark_on_image(
                task['src_path'],
                task['dst_path'],
                watermark_img=task['watermark_img'],
                anchor=task.get('anchor', (0.5,0.5)),
                output_format=task.get('output_format','png'),
                jpeg_quality=task.get('jpeg_quality',90),
                resize_to=task.get('resize_to', None)
            )
            return True, ''
        except Exception as e:
            return False, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = []
        for t in tasks:
            futures.append(ex.submit(worker, t))
        for i, f in enumerate(concurrent.futures.as_completed(futures), start=1):
            success, msg = f.result()
            if progress_callback:
                progress_callback(i, total, success, msg)
            results.append((success, msg))
    return results
