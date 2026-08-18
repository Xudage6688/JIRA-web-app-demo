"""
Affects Projects 分组逻辑（纯函数）
按 sp_team 聚合 JiraExtractor.get_affects_projects 返回的 results
供 pages/1_📊_Jira_Affects_Project.py 的 UI 层调用，便于单元测试
"""

from typing import Dict, List

UNKNOWN_TEAM_LABEL = "未分配 SP Team"


def group_projects_by_sp_team(results: List[Dict]) -> Dict[str, List[str]]:
    """按 sp_team 分组聚合 affects_projects

    Args:
        results: JiraExtractor.get_affects_projects 返回的列表，每个元素含
                 sp_team(str|None) 与 affects_projects(List[str]|str|None)

    Returns:
        按 team 名字母序排列的有序字典 {team_name: [sorted_projects]}
        空 sp_team 归入 UNKNOWN_TEAM_LABEL，始终排在最后
        同一项目可出现在多个 team 下（由不同 team 的 issue 提及）
        过滤掉空字符串与 "NA"（大小写不敏感）
        team 名与项目名均按小写字母序排序
    """
    teams_to_projects: Dict[str, set] = {}

    for result in results:
        raw_team = result.get("sp_team")
        team = (str(raw_team).strip() if raw_team is not None else "") or UNKNOWN_TEAM_LABEL

        raw_projects = result.get("affects_projects")
        if raw_projects is None:
            continue
        if isinstance(raw_projects, str):
            projects_iter = [p.strip() for p in raw_projects.split(",")]
        else:
            projects_iter = list(raw_projects)

        team_set = teams_to_projects.setdefault(team, set())
        for project in projects_iter:
            project_clean = str(project).strip()
            if project_clean and project_clean.upper() != "NA":
                team_set.add(project_clean)

    sorted_teams = sorted(
        teams_to_projects.keys(),
        key=lambda t: (t == UNKNOWN_TEAM_LABEL, t.lower()),
    )
    return {
        team: sorted(teams_to_projects[team], key=str.lower)
        for team in sorted_teams
    }
