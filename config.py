import subprocess
import logging
import logging.config
import re
import os
import sys
import argparse
from typing import Tuple


def configure_logging():
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s]: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
        }
    })


def check_permission():
    if os.geteuid() != 0:
        sys.exit("Config must be run as root!")


def setup():
    logging.info("Setting up system...")
    subprocess.check_call('apt update', shell=True)
    subprocess.check_call('apt upgrade', shell=True)

    packages = [
        'unzip',
        'chromium-browser',
    ]
    subprocess.check_call('apt install -y {}'.format(' '.join(packages)), shell=True)
    logging.info("Finished setting up system")


def get_display(display_port: int) -> int:
    lines = subprocess.check_output('tvservice -l', shell=True).decode('UTF-8').split('\n')

    # Display Number 2, type HDMI 0
    pattern = re.compile(r"Display Number\s+(\d+),\s+type HDMI {}".format(display_port))

    for line in lines:
        match = pattern.match(line)
        if match:
            value = match.group(1)
            logging.info("Found display {}".format(value))
            return int(value)

    raise Exception("Unable to identify display number!")


def get_resolution(display: int, is_tv: bool) -> Tuple[int, int, int]:
    cmd = 'tvservice -v {} -m {}'.format(display, 'CEA' if is_tv else 'DMT')
    lines = subprocess.check_output(cmd, shell=True).decode('UTF-8').split('\n')

    # mode 16: 1920x1080 @ 60Hz 16:9, clock:148MHz progressive 3D:TopBot|SbS-HH
    pattern = re.compile(r".*?mode (\d+): (\d+)x(\d+).*?")

    for line in lines:
        if 'prefer' in line:
            matcher = pattern.match(line)
            mode = int(matcher.group(1))
            x = int(matcher.group(2))
            y = int(matcher.group(3))
            logging.info(line)
            logging.info("Found resolution mode {}, {}x{}".format(mode, x, y))
            return mode, x, y

    raise Exception("Unable to identify display resolution!")


def update_xinitrc():
    logging.info("Updating xinitrc")

    file = '/home/pi/.xinitrc'
    content = open(file, 'r').read().split('\n')

    with open(file, 'w') as fp:
        for line in content:
            if "chromium-browser" in line:
                url = "http://open.spotify.com"
                agent = "Mozilla/5.0 (X11; CrOS armv7l 12371.89.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36"
                cmd = "chromium-browser --app={} --window-size=$SCREENSIZE --window-position=0,0 --user-agent={}".format(url, agent)

                logging.info("Setting browser cmd \"{}\"".format(cmd))
                fp.write(cmd + "\n")
            else:
                fp.write(line + "\n")
    logging.info("Finished updating xinitrc")


def chromium_setup():
    logging.info("Install Widevine...")
    subprocess.check_call('cp libwidevinecdm.so /usr/lib/chromium-browser', shell=True)
    logging.info("Widevine Setup Complete")


def update_pi_config(is_tv: bool, mode: int):
    file = '/boot/config.txt'

    logging.info("Updating {}".format(file))

    # backup
    subprocess.check_call('cp {} {}'.format(file, file + '.bk'), shell=True)

    content = open(file, 'r').read().split('\n')

    props = {
        'hdmi_group': 1 if is_tv else 0,
        'hdmi_mode': mode,
    }

    with open(file, 'w') as fp:
        for line in content:
            key = line.split('=')[0]
            if key not in props.keys():
                fp.write(line + "\n")

        for key, value in props.items():
            fp.write("{}={}\n".format(key, value))


def configure(run_setup: bool, display_port: int, is_tv: bool):
    check_permission()
    configure_logging()
    if run_setup:
        setup()
    display = get_display(display_port)
    mode, x, y = get_resolution(display, True)
    update_xinitrc()
    chromium_setup()
    update_pi_config(is_tv, mode)


parser = argparse.ArgumentParser()
parser.add_argument('--no-setup', action='store_true', default=False)
parser.add_argument('--display', type=int, default=0)

group = parser.add_mutually_exclusive_group()
group.add_argument('--tv', action='store_true', default=False)
group.add_argument('--monitor', action='store_true', default=False)

args = parser.parse_args()

configure(not args.no_setup, args.display, args.tv)
