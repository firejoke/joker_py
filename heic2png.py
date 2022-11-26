#!C:\Program Files\Python311\python.exe
# -*- coding: utf-8 -*-
# Author      : ShiFan
# Created Date: 2022/11/26 15:54
"""The Module Has Been Build for Convert heic to png"""
import argparse
from pathlib import Path

from PIL import Image, ExifTags
from pillow_heif import register_heif_opener
from datetime import datetime
from piexif import load as exif_load, dump as exif_dump, TAGS, TYPES, ImageIFD


register_heif_opener()


def convert(file_path):
    print(f"check {file_path}")
    image = Image.open(file_path)
    image_exif = image.getexif()
    if image_exif:
        # Make a map with tag names and grab the datetime
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in image_exif.items()
            if k in ExifTags.TAGS and not isinstance(v, bytes)
        }
        date = datetime.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
        
        # Load exif data via piexif
        _exif = image.info["exif"]
        exif_dict = exif_load(_exif)
        
        # Update exif data with orientation and datetime
        exif_dict["0th"][ImageIFD.DateTime] = date.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict["0th"][ImageIFD.Orientation] = 1
        for tag, values in exif_dict.items():
            if values:
                for k, v in values.items():
                    if TAGS[tag][k]["type"] == TYPES.Undefined:
                        if not isinstance(v, bytes):
                            exif_dict[tag][k] = bytes(v)
        # print(exif_dict)
        exif_bytes = exif_dump(exif_dict)
        
        # Save image as jpeg
        print(f"保存为{file_path[:-5]}.png")
        image.save(f"{file_path[:-5]}.png", "png", exif=exif_bytes)
    else:
        print(f"Unable to get exif data for {file_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="转换目录下的所有heic图片为png，或只转换一张。",
    )
    parser.add_argument("source", help="目录或图片的路径。")
    args = parser.parse_args()
    path = Path(args.source)
    if path.is_dir():
        for _path in path.iterdir():
            if _path.is_file() and _path.name.lower().endswith("heic"):
                convert(_path.absolute().as_posix())
    elif path.is_file():
        convert(path.absolute().as_posix())
    else:
        print("不是有效路径。")
    print("结束。")

