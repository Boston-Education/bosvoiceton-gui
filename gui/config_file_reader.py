from configparser import ConfigParser, ExtendedInterpolation, SectionProxy


def obtain_cfg_info(cfg_directory: str) -> SectionProxy:
    config = ConfigParser(interpolation=ExtendedInterpolation())
    config.read(cfg_directory, encoding="utf-8")

    return config