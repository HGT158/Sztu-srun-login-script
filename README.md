# SZTU 宿舍网络自动登录脚本

> 250726备注：最近校园网疑似新增了多设备共享检测，目前仅感知到了ttl检测。解决方法如下：
> ~~有这ban路由器的功夫不如想想办法提高一下贵校的网络质量😅~~
```shell
# 使用 nftables 固定 TTL 为 64：
nft add table inet ttl64
nft add chain inet ttl64 postrouting { type filter hook postrouting priority -150\; policy accept\; }
nft add rule inet ttl64 postrouting counter ip ttl set 64

# 使用 iptables 固定 TTL 为 64：
iptables -t mangle -A POSTROUTING -j TTL --ttl-set 64
```

> Reference: 这份代码偷自[北京理工大学深澜校园网登录python脚本](https://github.com/coffeehat/BIT-srun-login-script)并加以修改，在此感谢这位大佬的辛勤付出。

> 为了解决 SZTU 北区研究生宿舍的校园网络无法使用路由器 PPPoE 自动登录、长时间无流量或超时会自动掉线的问题而抓包设计的 Python 脚本。
> ~~这网络确实有点溺智~~

## 功能特点

- 自动登录
- 断线自动重连
- 支持容器化部署

## 使用方法

在宿舍路由器局域网内设备运行该脚本，在脚本运行期间即可实现上述功能。

### 1. 不使用容器

需要先编辑`main.py`文件，补全校园网账号、密码，随后执行。

```shell
pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple # 安装requests库
python main.py # 运行脚本
```

### 2. 使用容器

在项目目录下运行

```shell
docker build --tag sztu-network-autologin .
docker run -d --name sztu-network-autologin \
           -e   USER_ID=你的校园网账号 \
           -e   PASSWORD=你的校园网密码 \
           -e   CHECK_INTERVAL=5 \
           sztu-network-autologin
```
