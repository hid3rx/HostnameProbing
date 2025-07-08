# coding=utf-8

# python -m pip install lxml

import requests, urllib3, argparse, traceback, time, os, threading, logging
from requests.exceptions import ConnectTimeout, ConnectionError, ReadTimeout
from concurrent import futures
from datetime import datetime
from lxml import etree

# 禁用https警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 日志设置
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('log.txt')
fh.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(ch)

#
# =================== [ 全局设置 ] ===================
#

# 线程并发数
THREADS = 5

# 每个线程发起登录后暂停时长，单位秒
DELAY = 1

# 是否使用代理
USE_PROXY = False

# 设置代理
PROXIES = {
    "http": "http://127.0.0.1:8083",
    "https": "http://127.0.0.1:8083"
}

#
# =================== [ 扫描函数 ] ===================
#

def run(address, hostname):
    time.sleep(DELAY)

    headers = requests.utils.default_headers()
    headers.update({
        "Host": hostname,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
        "Connection": "close",
    })

    if not address.startswith("http://") and not address.startswith("https://"):
        address = "http://" + address

    try:
        response = requests.get(address, verify=False, headers=headers, 
            allow_redirects=False, timeout=5, proxies=PROXIES if USE_PROXY else None)
        html = etree.HTML(response.text)
        title = []
        if html is not None:
            title = html.xpath('//title/text()')
        title = title[0] if title else "NULL"
        logger.info("hostname:{0:<20}\t\taddress:{1:<20}\tcode:{2:<3}\tlen:{3:<5}\ttitle:{4}".format(hostname, address, response.status_code, len(response.content), title))
    except (ConnectTimeout, ConnectionError, ReadTimeout) as e:
        print(f"[x] address:{address}\t{hostname}\tConnect error")
    except Exception as e:
        print(f"[x] address:{address}\t{hostname}\tEncounter error: {e}, detail:")
        print(traceback.format_exc())

#
# =================== [ 启动多线程扫描 ] ===================
#

TASKS = set()

# 并发运行爆破函数
def concurrent_run(executor, addresses: list, hostnames: list):
    global TASKS
    for address in addresses:
        address = address.rstrip()
        if not address:
            continue
        for hostname in hostnames:
            hostname = hostname.rstrip()
            if not hostname:
                continue
            # 如果队列过长就等待
            if len(TASKS) >= THREADS:
                _, TASKS = futures.wait(TASKS, return_when=futures.FIRST_COMPLETED)
            # 新建线程
            t = executor.submit(run, address, hostname)
            TASKS.add(t)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Hostname probing tool')
    parser.add_argument("-A", "--addresses", default="addresses.txt", type=str, help="地址列表文件，每行一个URL，接受 127.0.0.1:9000 和 http://127.0.0.1:9000 两种格式")
    parser.add_argument("-H", "--hostnames", default="hostnames.txt", type=str, help="域名列表文件，每行一个域名")
    args = parser.parse_args()
    if args.addresses and args.hostnames:
        # 读取地址列表
        try:
            with open(args.addresses, "r", encoding="utf-8") as f:
                addresses = f.readlines()
        except Exception as e:
            print(f"[x] Cannot open '{args.addresses}' file {e}")
            os._exit(0)

        # 读取域名列表
        try:
            with open(args.hostnames, "r", encoding="utf-8") as f:
                hostnames = f.readlines()
        except Exception as e:
            print(f"[x] Cannot open '{args.hostnames}' file {e}")
            os._exit(0)
        
        # 写入日志
        logger.info(f"\n# Begin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 多线程扫描
        with futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
            try:
                concurrent_run(executor, addresses, hostnames)
                print("[!] Wait for all threads exit.")
                futures.wait(TASKS, return_when=futures.ALL_COMPLETED)
            except KeyboardInterrupt:
                print("[!] Get Ctrl-C, wait for all threads exit.")
                futures.wait(TASKS, return_when=futures.ALL_COMPLETED)
    else:
        parser.print_help()
