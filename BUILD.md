# 龙虾写书 — 打包说明

## 环境要求

- Python 3.12
- Windows x64
- Visual Studio Build Tools（Nuitka 编译需要 C++ 编译器）

## 安装依赖

```bash
pip install fpdf2 pillow pymysql cryptography
pip install pyinstaller          # 备用方案
pip install nuitka zstandard     # 正式打包（原生编译，防反编译）
```

## 打包命令

### 正式版（Nuitka，推荐）

编译为原生机器码，无 .pyc，防止反编译。

```bash
py -3 -m nuitka ^
  --onefile ^
  --windows-console-mode=disable ^
  --windows-product-name="龙虾写书" ^
  --windows-file-version="1.0.0.0" ^
  --windows-company-name="LobsterBook" ^
  --enable-plugin=tk-inter ^
  --output-filename="龙虾写书.exe" ^
  --assume-yes-for-downloads ^
  --jobs=4 ^
  lobster_book.py
```

首次编译约 5-10 分钟（需下载 Dependency Walker，后续有缓存会快很多）。

### 调试版（PyInstaller，快速迭代用）

```bash
py -3 -m PyInstaller ^
  --onefile --windowed ^
  --name "龙虾写书" ^
  --hidden-import pymysql ^
  --hidden-import pymysql.connections ^
  --hidden-import pymysql.cursors ^
  lobster_book.py
```

输出在 `dist/龙虾写书.exe`，移动到根目录后删除 `dist/` `build/` `*.spec`。

## 打包后清理

```bash
rd /s /q lobster_book.dist
rd /s /q lobster_book.build
rd /s /q lobster_book.onefile-build
```

## 数据库

激活码数据库：`106.53.86.215:3306`，库名 `lobster_book`，表 `activation_codes`。

新增激活码（在数据库直接执行）：

```sql
-- 通用码（可解锁任意书）
INSERT INTO activation_codes (code, book_id) VALUES ('XXXX-XXXX-XXXX-XXXX', 0);

-- 指定书籍码（book_id 对应广场书籍 id 1-6）
INSERT INTO activation_codes (code, book_id) VALUES ('XXXX-XXXX-XXXX-XXXX', 1);
```

## 发布目录结构

发给用户的文件夹只需包含：

```
龙虾写书/
├── 龙虾写书.exe   ← 唯一可执行文件
└── 点击启动.bat   ← 可选，双击同效果
```

源码 `lobster_book.py` 不要放进发布包。
