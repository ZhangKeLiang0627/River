# River-dev
# by Hugo@kkl

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
