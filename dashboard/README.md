# Local dashboard

五页经营诊断界面；静态聚合 JSON，无后端、无认证要求、无外部跟踪器。

从此目录执行：

```sh
npm ci
npm run build
npm run preview
```

Node 24 / npm；preview 打印本地地址。不要直接双击 index.html。Vite base 为相对路径，路由使用 hash。页面内筛选仅作用于标明的图表，冻结 KPI 不随局部筛选变动。

`npm run build` 包含日期与数据测试。可选浏览器检查需自行安装 Playwright 并具备 Edge；先运行 preview，再执行 `node tests/browser.test.cjs`。测试生成的截图、QA 文件只留在本地。

聚合源见 [analysis outputs](../analysis/outputs)。从仓库根目录可执行 `python dashboard/scripts/build_dashboard_data.py` 重建 extract。若自行重新分析，先核对全部上游 QA，再重建；禁止自动发布行级数据。

[返回项目](../README.md)
