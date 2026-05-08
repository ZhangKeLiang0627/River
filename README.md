<p align="center">
  <img width="18%" align="center" src="https://github.com/ZhangKeLiang0627/River-dev/blob/main/docs/source/river.png?raw=true" alt="logo">
</p>
  <h1 align="center">
  River
</h1>
<p align="center">
  A icon generator based on PySide6
</p>

---

## Install

```bash
# 创建python虚拟环境
conda create -n pyside6 python=3.11

# 激活环境
conda activate pyside6

# 安装pyside6组件
pip install pyside6

# 安装依赖
pip install -r requirements.txt

# 编译resources.qrc
pyside6-rcc app/resources/resources.qrc -o app/resources/resources_rc.py

# 运行项目
python main.py
```
