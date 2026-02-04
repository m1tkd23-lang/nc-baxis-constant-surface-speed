"""
アプリケーションのエントリポイント。
CLI / GUI / Web いずれの場合も、このファイルは"薄く"保つ。
"""
from src.nc_baxis_constant_surface_speed.core import main


if __name__ == "__main__":
    main()
