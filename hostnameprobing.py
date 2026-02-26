# coding=utf-8

import argparse, chardet, logging, os, random, requests, traceback, time, threading, urllib3
from concurrent import futures
from datetime import datetime
from lxml import etree
from requests.exceptions import ConnectTimeout, ConnectionError, ReadTimeout

# 禁用https警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#
# =================== [ 全局设置 ] ===================
#

configs = \
{
    # 超时时间，单位秒
    "timeout": 10,

    # 线程并发数
    "threads": 10,
    
    # 每个线程发起请求后暂停时长，单位秒
    "delay": 1,

    # 扫描日志
    "logfile": "log.txt",

    # 是否使用代理
    "use_proxy": False,

    # 设置代理
    "proxies": {
        "http": "http://127.0.0.1:8080",
        "https": "http://127.0.0.1:8080"
    },

    # 自定义headers
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
        "Connection": "close",
    }
}

# 互斥锁
locks = {
    "log": threading.Lock()
}

#
# =================== [ 功能函数 ] ===================
#

# 日志输出
def log(message: str):
    with locks["log"]:
        print(message)
        with open(configs["logfile"], "a", encoding="utf-8") as fout:
            fout.write(message + "\n")

#
# =================== [ 扫描函数 ] ===================
#

def run(address, hostname):
    time.sleep(configs["delay"])

    headers = requests.utils.default_headers()
    headers.update(configs["headers"])
    random_ip = ".".join(str(random.randint(0,255)) for _ in range(4))
    headers.update({
        "Host": hostname,
        "X-Forwarded-For": random_ip,
        "X-Originating-IP": random_ip,
        "X-Remote-IP": random_ip,
        "X-Remote-Addr": random_ip,
        "X-Real-IP": random_ip
    })
    proxies = configs["proxies"] if configs["use_proxy"] else None

    if not address.startswith("http://") and not address.startswith("https://"):
        address = "http://" + address

    try:
        response = requests.get(address, verify=False, headers=headers, allow_redirects=False, timeout=configs["timeout"], proxies=proxies)
        charset = chardet.detect(response.content)
        charset = charset['encoding'] if charset['encoding'] else "utf-8"
        html = etree.HTML(response.content.decode(charset))
        title = []
        if html is not None:
            title = html.xpath('//title/text()')
        title = title[0] if title else "NULL"
        log("hostname:{0:<50}\t\taddress:{1:<30}\tcode:{2:<3}\tlen:{3:<5}\ttitle:{4}".format(hostname, address, response.status_code, len(response.content), title))
    except (ConnectTimeout, ConnectionError, ReadTimeout) as e:
        print(f"[x] address:{address}\t{hostname}\tConnect error")
    except Exception as e:
        print(f"[x] address:{address}\t{hostname}\tEncounter error: {e}, detail:")
        print(traceback.format_exc())

#
# =================== [ 启动多线程扫描 ] ===================
#

# 并发运行爆破函数
def concurrent_run(executor, tasks, addresses: list, hostnames: list):
    for address in addresses:
        if not address:
            continue
        for hostname in hostnames:
            if not hostname:
                continue
            # 如果队列过长就等待
            if len(tasks) >= configs["threads"]:
                _, tasks = futures.wait(tasks, return_when=futures.FIRST_COMPLETED)
            # 新建线程
            tasks.add(executor.submit(run, address, hostname))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Hostname probing tool')
    parser.add_argument("-A", "--addresses", default="addresses.txt", type=str, help="地址列表文件，每行一个URL，接受 127.0.0.1:9000 和 http://127.0.0.1:9000 两种格式")
    parser.add_argument("-H", "--hostnames", default="hostnames.txt", type=str, help="域名列表文件，每行一个域名")
    args = parser.parse_args()
    if args.addresses and args.hostnames:
        # 读取地址列表
        addresses = []
        try:
            with open(args.addresses, "r", encoding="utf-8") as fin:
                for line in fin:
                    line = line.strip()
                    if not line:
                        continue
                    addresses.append(line)
        except Exception as e:
            print(f"[x] Cannot open '{args.addresses}' file {e}")
            os._exit(0)

        # 读取域名列表
        hostnames = []
        try:
            with open(args.hostnames, "r", encoding="utf-8") as fin:
                for line in fin:
                    line = line.strip()
                    if not line:
                        continue
                    hostnames.append(line)
        except Exception as e:
            print(f"[x] Cannot open '{args.hostnames}' file {e}")
            os._exit(0)
        
        # 写入日志
        log(f"\n# Begin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 多线程扫描
        tasks = set()
        with futures.ThreadPoolExecutor(max_workers=configs["threads"]) as executor:
            try:
                concurrent_run(executor, tasks, addresses, hostnames)
                print("[!] Wait for all threads exit.")
                futures.wait(tasks, return_when=futures.ALL_COMPLETED)
            except KeyboardInterrupt:
                print("[!] Get Ctrl-C, wait for all threads exit.")
                futures.wait(tasks, return_when=futures.ALL_COMPLETED)
    else:
        parser.print_help()
