# 实施计划：QA 工具集开源迁移与脱敏

## 概述

将 `D:/pythonProject/webtools` 的 DevOps 自动化工具平台迁移至 `D:/personal/QIMA-qa-tools`，进行全面信息脱敏后开源到 GitHub 作为简历展示项目。

---

## 脱敏映射表

| 原始内容 | 脱敏后内容 |
|---------|-----------|
| QIMA / qima | 某法资检测公司 / Demo Company |
| qima.atlassian.net | demo.atlassian.net |
| jenkins.qima.com | jenkins.example.com |
| asiainspection | demo-org |
| daisy.liu@qima.com | demo@example.com |
| Daisy, Elle, Lucas, Nina, Sam | Demo User, User A, User B |
| aca-new, back-office-cloud | demo-service-a, demo-service-b |
| filter_id: 20334 | filter_id: 10001 |
| customfield_12605 | customfield_10001 |
| 所有真实 Token | YOUR_XXX_TOKEN_HERE |

---

## 实施步骤

### Phase 1: 项目骨架搭建
1. 创建目录结构
2. 创建 .gitignore
3. 创建 LICENSE (MIT)

### Phase 2: 核心代码迁移与脱敏
4. 迁移 modules/ 目录
5. 迁移 pages/ 目录
6. 迁移 circleCi/ 目录
7. 迁移 app.py

### Phase 3: 配置文件模板化
8. 创建 users_config.example.json
9. 创建 circleci-services.example.txt
10. 迁移 requirements.txt

### Phase 4: 文档重写
11. 重写 README.md
12. 创建 CHANGELOG.md
13. 创建 CONTRIBUTING.md
14. 迁移 docs/ 目录

### Phase 5: 测试文件迁移
15. 迁移 tests/ 目录
16. 运行测试验证

### Phase 6: 最终验证
17. 全局敏感词搜索（qima, QIMA, Daisy, @qima.com, asiainspection）
18. 启动应用验证

---

## 成功标准

- [ ] 所有代码文件完成迁移
- [ ] 全局搜索无敏感关键词残留
- [ ] 所有单元测试通过
- [ ] 测试覆盖率 >= 85%
- [ ] README.md 专业完整
- [ ] 应用可正常启动