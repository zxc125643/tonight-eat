# 今晚吃什么 🍽️

两大一小（小的才 1 岁多，不能吃重口味辛辣）的家常晚饭推荐器。

## 功能

- **50 套完整菜谱**：每套 = 一荤 + 一素 + 一汤（不是单个菜）
- **页面只显示 5 套**，底部提示"还有 45 套，点「抽今晚」带出来"
- **抽今晚**：从 50 套里随机抽一套，抽中的显示在顶部（绿色高亮）
  - 如果抽中的不在前 5 套里，会临时插到列表顶部（方便查看做法）
- **吃过了标记**：每个卡片有按钮，点击后变"✓ 吃过了"（绿色），再点取消
  - 标记会持久化保存，下次打开还在
- **筛选**：全部 / 快手 / 清淡 / 下饭 / 少油
- **复制买菜单**：一键复制食材清单（去菜市场用）

## 技术栈

- **前端**：单文件 HTML（vanilla JS，无框架）
- **后端**：Python `http.server`（无 Flask/Django）
- **数据**：JSON 文件（`menus.json`），不写死在 HTML 里
- **部署**：systemd 服务（开机自启 + 崩溃重启）

## 文件结构

```
tonight-eat/
├── index.html          # 前端页面
├── server.py             # 后端 API
├── menus.json            # 菜谱数据（50 套）
├── fetch_recipes.py      # 抓取脚本（从下厨房抓新菜谱）
├── tonight-eat.service   # systemd 服务
└── .gitignore
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/menus` | 获取所有菜谱 |
| GET | `/api/menus/count` | 菜谱数量 |
| POST | `/api/menus` | 新增菜谱 |
| PUT | `/api/menus` | 更新菜谱（如"吃过了"标记） |
| DELETE | `/api/menus?id=xxx` | 删除菜谱 |

## 部署

### 1. 安装 systemd 服务

```bash
sudo -S -p '' cp tonight-eat.service /etc/systemd/system/
sudo -S -p '' systemctl daemon-reload
sudo -S -p '' systemctl enable tonight-eat
sudo -S -p '' systemctl start tonight-eat
```

### 2. 配置 cron 定时抓取（可选）

```bash
crontab -e
# 添加：每天 6:00 自动抓新菜谱
0 6 * * * cd /path/to/tonight-eat && /usr/bin/python3 fetch_recipes.py >> fetch.log 2>&1
```

### 3. 访问

```
http://<你的IP>:8095/
```

## 后续补充菜谱

### 方式一：自动抓取（已配好）

- 每天早上 6 点，cron 自动跑 `fetch_recipes.py`
- 从下厨房搜"王刚""厨师长教你"，抓新菜谱
- 自动去重（已有的不重复加），增量写入 `menus.json`

### 方式二：手动加（随时可以）

直接编辑 `menus.json`，每套菜谱格式：

```json
{
  "id": "唯一标识",
  "title": "菜名1 · 菜名2 · 菜名3",
  "time": "30 分钟",
  "tags": ["下饭", "快手"],
  "why": "推荐理由",
  "shop": ["食材1", "食材2"],
  "dishes": [
    {"role": "大菜", "name": "菜名", "ing": ["食材"], "steps": ["步骤"]},
    {"role": "大菜", "name": "菜名", "ing": ["食材"], "steps": ["步骤"]},
    {"role": "小菜", "name": "菜名", "ing": ["食材"], "steps": ["步骤"]}
  ],
  "eaten": false
}
```

**注意**：
- 确保每套都是"一套菜"（3 道菜：一荤+一素+一汤），不要只加单个菜
- 小孩才 1 岁多，不能吃重口味辛辣，加菜谱时注意标注"清淡""少油"标签

## 局域网地址

```
http://192.168.3.6:8095/
```

## 备份

每次大改动前，备份到 `backups/YYYYMMDD-HHMMSS/`：

```bash
BACKUP_DIR="backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp menus.json server.py fetch_recipes.py index.html tonight-eat.service "$BACKUP_DIR/"
```

恢复方法：

```bash
cp backups/<备份目录>/* .
sudo -S -p '' systemctl restart tonight-eat
```
