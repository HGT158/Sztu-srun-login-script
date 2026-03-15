# SZTU 宿舍网络自动登录脚本

> Reference: 这份代码偷自[SZTU 宿舍网络自动登录脚本](https://github.com/AdamXuD/Sztu-srun-login-script)并加以修改，在此感谢这位大佬的辛勤付出。


## 功能特点

- Windows 图形界面客户端（开箱即用 exe）
- 自动登录
- 断线自动重连
- 支持多运营商选择（联通 / 移动 / 电信 / 校园网）
- 开机自启动
- 支持容器化部署

## 使用方法

### 方式一：Windows 图形界面（推荐）

下载并解压Releases的最新版本安装包  
直接运行 里面的`SZTU校园网登录助手.exe`即可，无需安装 Python 环境。

1. 填写校园网账号、密码，选择运营商
2. 点击「登 录」完成认证
3. 勾选「自动重连」并设置检测间隔（默认 300 秒），登录成功后自动监控网络，断线即重连
4. 勾选「开机自启」可实现开机后自动在后台维持连接

> 账号密码保存在本机 `%APPDATA%\SZTUCampusLogin\.login_config.json`，不会上传或泄露。  
> 首次运行可能出现 Windows SmartScreen 提示，点击「更多信息」→「仍要运行」即可，仅首次需要。

---

### 方式二：命令行脚本

在宿舍路由器局域网内设备运行该脚本，在脚本运行期间即可实现上述功能。

需要先编辑 `main.py` 文件，补全校园网账号、密码，随后执行。

```shell
pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple # 安装requests库
python main.py # 运行脚本
```

### 方式三：Docker 容器

在项目目录下运行

```shell
docker build --tag sztu-network-autologin .
docker run -d --name sztu-network-autologin \
           -e   USER_ID=你的校园网账号 \
           -e   PASSWORD=你的校园网密码 \
           -e   CHECK_INTERVAL=5 \
           sztu-network-autologin
```

---

### 重新打包 exe（开发者）

```shell
pip install pyinstaller pyqt5 requests
python -m PyInstaller build.spec --clean --noconfirm
```

打包产物在 `dist/SZTU校园网登录助手/` 目录下。
