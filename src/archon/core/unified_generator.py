import json
from pathlib import Path
from typing import Dict, Any, List
from archon.core.html_generator import json_file_to_section

UNIFIED_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Archon One - Unified Scan Report</title>
    <style>
        :root {
            --bg-color: #FFFFFF;
            --card-color: #F8F8F8;
            --text-color: #212529;
            --border-color: #DEE2E6;
            --primary-btn: #212529;
            --primary-btn-hover: #000000;
            --secondary-btn: #FFFFFF;
            --critical-color: #E53935;
            --warning-color: #FB8C00;
            --success-color: #4CAF50;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-family);
            background-color: var(--bg-color);
            color: var(--text-color);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* Sidebar navigation */
        .sidebar {
            width: 320px;
            border-right: 1px solid var(--border-color);
            background-color: var(--card-color);
            display: flex;
            flex-direction: column;
            padding: 20px 0;
        }

        .brand {
            font-size: 1.25rem;
            font-weight: bold;
            text-align: center;
            padding: 10px 0 20px 0;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 5px;
        }

        .brand span {
            font-size: 0.8rem;
            font-weight: normal;
            color: #6c757d;
        }

        .nav-links {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 15px;
            padding: 15px;
            overflow-y: auto;
            flex-grow: 1;
        }

        .module-group {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .module-title {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #6c757d;
            margin-bottom: 4px;
            padding-left: 8px;
        }

        .nav-link {
            padding: 8px 12px;
            text-decoration: none;
            color: var(--text-color);
            border-radius: 6px;
            font-weight: 500;
            font-size: 0.85rem;
            cursor: pointer;
            transition: background-color 0.2s;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .nav-link:hover {
            background-color: var(--border-color);
        }

        .nav-link.active {
            background-color: var(--primary-btn);
            color: var(--bg-color);
        }

        .search-badge {
            font-size: 0.75rem;
            font-weight: bold;
        }

        /* Main Workspace */
        .main-workspace {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            height: 100%;
            position: relative;
            overflow: hidden;
        }

        /* Header block */
        .header {
            height: 80px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 30px;
            background-color: var(--bg-color);
        }

        .header-info h2 {
            font-size: 1.3rem;
            font-weight: 700;
        }

        .header-info p {
            font-size: 0.8rem;
            color: #6c757d;
            margin-top: 2px;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .search-box {
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 0.85rem;
            width: 280px;
        }

        /* Content panels */
        .content {
            flex-grow: 1;
            padding: 30px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        /* Summary Cards Grid */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }

        .summary-card {
            background-color: var(--card-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }

        .summary-card-title {
            font-size: 0.8rem;
            color: #6c757d;
            font-weight: 600;
            text-transform: uppercase;
        }

        .summary-card-value {
            font-size: 1.75rem;
            font-weight: 700;
        }

        .summary-card.critical {
            border-left: 4px solid var(--critical-color);
        }

        .summary-card.warning {
            border-left: 4px solid var(--warning-color);
        }

        .summary-card.success {
            border-left: 4px solid var(--success-color);
        }

        /* Table Card Container */
        .table-card {
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .table-card-header {
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            background-color: var(--card-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .table-card-title {
            font-size: 1rem;
            font-weight: 600;
        }

        .table-actions {
            display: flex;
            gap: 8px;
        }

        /* Interactive Tables */
        .table-responsive {
            overflow-x: auto;
            width: 100%;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.875rem;
        }

        th {
            background-color: var(--card-color);
            font-weight: 600;
            padding: 12px 15px;
            border-bottom: 2px solid var(--border-color);
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
            z-index: 2;
        }

        th:hover {
            background-color: var(--border-color);
        }

        td {
            padding: 12px 15px;
            border-bottom: 1px solid var(--border-color);
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        tr:hover {
            background-color: #f1f3f5;
            cursor: pointer;
        }

        tr.selected {
            background-color: #e8f0fe !important;
        }

        tr:nth-child(even) {
            background-color: #fafafa;
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 3px 8px;
            font-size: 0.75rem;
            font-weight: bold;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .badge-critical {
            background-color: #ffebee;
            color: var(--critical-color);
        }

        .badge-warning {
            background-color: #fff3e0;
            color: var(--warning-color);
        }

        .badge-success {
            background-color: #e8f5e9;
            color: var(--success-color);
        }

        /* Fullscreen Mode */
        .fullscreen-active {
            position: fixed !important;
            top: 0;
            left: 0;
            width: 100vw !important;
            height: 100vh !important;
            z-index: 1000;
            background-color: white;
            padding: 20px;
            overflow: auto;
        }

        /* Pagination Controls */
        .pagination-container {
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border-color);
            background-color: var(--card-color);
        }

        .pagination-info {
            font-size: 0.8rem;
            color: #6c757d;
        }

        .pagination-buttons {
            display: flex;
            gap: 5px;
        }

        /* Buttons */
        .btn {
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: opacity 0.2s;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }

        .btn:hover {
            opacity: 0.85;
        }

        .btn-primary {
            background-color: var(--primary-btn);
            color: var(--bg-color);
        }

        .btn-secondary {
            background-color: var(--secondary-btn);
            color: var(--primary-btn);
            border: 1px solid var(--primary-btn);
        }

        /* Slide-out details drawer */
        .details-drawer {
            position: fixed;
            top: 0;
            right: -450px;
            width: 450px;
            height: 100%;
            background-color: white;
            border-left: 1px solid var(--border-color);
            box-shadow: -4px 0 10px rgba(0,0,0,0.05);
            z-index: 500;
            transition: right 0.3s ease;
            display: flex;
            flex-direction: column;
        }

        .details-drawer.open {
            right: 0;
        }

        .drawer-header {
            padding: 20px;
            border-bottom: 1px solid var(--border-color);
            background-color: var(--card-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .drawer-header h3 {
            font-size: 1.1rem;
            font-weight: bold;
        }

        .drawer-close {
            font-size: 1.5rem;
            cursor: pointer;
            border: none;
            background: none;
        }

        .drawer-content {
            padding: 20px;
            overflow-y: auto;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .detail-row {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .detail-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            font-weight: 600;
            color: #6c757d;
        }

        .detail-value {
            font-size: 0.9rem;
            word-break: break-all;
            white-space: pre-wrap;
            line-height: 1.4;
        }

        .recommendation-box {
            background-color: #fff8e1;
            border-left: 4px solid var(--warning-color);
            padding: 15px;
            border-radius: 4px;
            margin-top: 10px;
        }
    </style>
</head>
<body>

    <!-- Sidebar -->
    <div class="sidebar">
        <div class="brand">
            Archon One
            <span>Unified Scan Report</span>
        </div>
        <ul class="nav-links" id="unified-nav">
            <!-- Populated dynamically via JS -->
        </ul>
    </div>

    <!-- Main Workspace -->
    <div class="main-workspace">
        <!-- Header -->
        <div class="header">
            <div class="header-info">
                <h2 id="header-title">Unified Repository Summary</h2>
                <p id="header-repo-details">Repository: Name | Date: Timestamp</p>
            </div>
            <div class="header-actions">
                <input type="text" id="global-search" class="search-box" placeholder="Search report content..." oninput="handleSearch(this.value)">
            </div>
        </div>

        <!-- Content Area -->
        <div class="content" id="main-content">
            <!-- Top Summary Grid -->
            <div class="summary-grid" id="summary-cards">
                <!-- Summary cards generated here -->
            </div>

            <!-- Table Card Container -->
            <div class="table-card" id="table-container">
                <div class="table-card-header">
                    <div class="table-card-title" id="section-title">Section Title</div>
                    <div class="table-actions">
                        <button class="btn btn-secondary" onclick="exportData('copy')">Copy</button>
                        <button class="btn btn-secondary" onclick="exportData('csv')">CSV</button>
                        <button class="btn btn-secondary" onclick="exportData('json')">JSON</button>
                        <button class="btn btn-secondary" onclick="exportData('md')">MD</button>
                        <button class="btn btn-secondary" onclick="toggleFullscreen()">Fullscreen</button>
                    </div>
                </div>
                
                <div class="table-responsive">
                    <table id="data-table">
                        <thead id="table-head">
                            <!-- Headers populated via JS -->
                        </thead>
                        <tbody id="table-body">
                            <!-- Rows populated via JS -->
                        </tbody>
                    </table>
                </div>

                <!-- Pagination Footer -->
                <div class="pagination-container">
                    <div class="pagination-info" id="pagination-info">Showing 0 to 0 of 0 entries</div>
                    <div class="pagination-buttons">
                        <button class="btn btn-secondary" id="btn-prev-page" onclick="changePage(-1)">Previous</button>
                        <button class="btn btn-secondary" id="btn-next-page" onclick="changePage(1)">Next</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Side Details Panel Drawer -->
        <div class="details-drawer" id="details-drawer">
            <div class="drawer-header">
                <h3 id="drawer-title">Item Details</h3>
                <button class="drawer-close" onclick="closeDrawer()">&times;</button>
            </div>
            <div class="drawer-content" id="drawer-content">
                <!-- Populated dynamically when row is selected -->
            </div>
        </div>
    </div>

    <!-- Embedded Data Payload -->
    <script>
        const reportData = __PAYLOAD_JSON__;
    </script>

    <!-- Interactive Client JS -->
    <script>
        let activeModuleIndex = 0;
        let activeSectionIndex = 0;
        let currentPage = 1;
        let rowsPerPage = 25;
        let searchQuery = "";
        let sortColIndex = -1;
        let sortDirection = 'asc';
        let filteredRows = [];
        let selectedRowIndex = -1;

        window.addEventListener('DOMContentLoaded', () => {
            initializeReport();
        });

        function initializeReport() {
            // Render Header Repo Info
            document.getElementById('header-repo-details').innerText = `Repository: ${reportData.repo_name} | Path: ${reportData.repo_path} | Scan Duration: ${reportData.duration}`;
            
            // Populate Nav Menu
            const navContainer = document.getElementById('unified-nav');
            navContainer.innerHTML = "";

            reportData.modules.forEach((mod, mIdx) => {
                const groupDiv = document.createElement('div');
                groupDiv.className = 'module-group';
                
                const title = document.createElement('div');
                title.className = 'module-title';
                title.innerText = mod.name;
                groupDiv.appendChild(title);

                mod.sections.forEach((sec, sIdx) => {
                    const li = document.createElement('li');
                    li.id = `link-${mIdx}-${sIdx}`;
                    li.className = 'nav-link';
                    
                    const textSpan = document.createElement('span');
                    textSpan.innerText = sec.title;
                    li.appendChild(textSpan);

                    const badgeSpan = document.createElement('span');
                    badgeSpan.id = `badge-${mIdx}-${sIdx}`;
                    badgeSpan.className = 'search-badge';
                    li.appendChild(badgeSpan);

                    li.onclick = () => switchSection(mIdx, sIdx);
                    groupDiv.appendChild(li);
                });

                navContainer.appendChild(groupDiv);
            });

            if (reportData.modules.length > 0 && reportData.modules[0].sections.length > 0) {
                switchSection(0, 0);
            }
        }

        function switchSection(mIdx, sIdx) {
            activeModuleIndex = mIdx;
            activeSectionIndex = sIdx;
            currentPage = 1;
            searchQuery = "";
            document.getElementById('global-search').value = "";
            sortColIndex = -1;
            sortDirection = 'asc';
            selectedRowIndex = -1;
            closeDrawer();

            // Set active class styling
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            const activeLi = document.getElementById(`link-${mIdx}-${sIdx}`);
            if (activeLi) activeLi.classList.add('active');

            const mod = reportData.modules[mIdx];
            const sec = mod.sections[sIdx];

            document.getElementById('header-title').innerText = `${mod.name} - ${sec.title}`;
            document.getElementById('section-title').innerText = sec.title;

            // Render summary cards
            const cardsContainer = document.getElementById('summary-cards');
            cardsContainer.innerHTML = "";
            const summaryCards = sec.summary_cards || reportData.summary_cards || [];
            summaryCards.forEach(card => {
                const div = document.createElement('div');
                div.className = `summary-card ${card.class || ''}`;
                div.innerHTML = `
                    <div class="summary-card-title">${card.title}</div>
                    <div class="summary-card-value">${card.value}</div>
                `;
                cardsContainer.appendChild(div);
            });

            // Render Headers
            const headContainer = document.getElementById('table-head');
            headContainer.innerHTML = "";
            const tr = document.createElement('tr');
            sec.headers.forEach((h, idx) => {
                const th = document.createElement('th');
                th.innerText = h;
                th.onclick = () => sortTable(idx);
                tr.appendChild(th);
            });
            headContainer.appendChild(tr);

            // Filter and draw
            applyFilterAndDraw();
        }

        function applyFilterAndDraw() {
            const mod = reportData.modules[activeModuleIndex];
            const sec = mod.sections[activeSectionIndex];
            if (!sec) return;

            if (!searchQuery) {
                filteredRows = [...sec.rows];
            } else {
                const q = searchQuery.toLowerCase();
                filteredRows = sec.rows.filter(row => {
                    return row.some(cell => String(cell).toLowerCase().includes(q));
                });
            }

            // Apply sorting
            if (sortColIndex !== -1) {
                filteredRows.sort((a, b) => {
                    let valA = a[sortColIndex];
                    let valB = b[sortColIndex];
                    
                    const numA = Number(valA);
                    const numB = Number(valB);
                    if (!isNaN(numA) && !isNaN(numB)) {
                        valA = numA;
                        valB = numB;
                    } else {
                        valA = String(valA).toLowerCase();
                        valB = String(valB).toLowerCase();
                    }

                    if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
                    if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
                    return 0;
                });
            }

            drawTable();
        }

        function drawTable() {
            const bodyContainer = document.getElementById('table-body');
            bodyContainer.innerHTML = "";

            if (filteredRows.length === 0) {
                const sec = reportData.modules[activeModuleIndex].sections[activeSectionIndex];
                const cols = sec ? sec.headers.length : 1;
                bodyContainer.innerHTML = `<tr><td colspan="${cols}" style="text-align: center; color: #6c757d;">No data available.</td></tr>`;
                document.getElementById('pagination-info').innerText = "Showing 0 to 0 of 0 entries";
                return;
            }

            const startIdx = (currentPage - 1) * rowsPerPage;
            const endIdx = Math.min(startIdx + rowsPerPage, filteredRows.length);

            for (let i = startIdx; i < endIdx; i++) {
                const row = filteredRows[i];
                const tr = document.createElement('tr');
                if (i === selectedRowIndex) tr.className = 'selected';
                
                tr.onclick = () => selectRow(i, tr);

                row.forEach(cell => {
                    const td = document.createElement('td');
                    const text = String(cell);
                    if (text === "Critical" || text === "High" || text === "Medium" || text === "Low") {
                        td.innerHTML = `<span class="badge badge-${text.toLowerCase()}">${text}</span>`;
                    } else {
                        td.innerText = text;
                    }
                    tr.appendChild(td);
                });
                bodyContainer.appendChild(tr);
            }

            document.getElementById('pagination-info').innerText = `Showing ${startIdx + 1} to ${endIdx} of ${filteredRows.length} entries`;
        }

        function handleSearch(val) {
            searchQuery = val;
            currentPage = 1;
            applyFilterAndDraw();

            // Calculate search hit badges across all sections and modules
            const q = val.toLowerCase().trim();
            reportData.modules.forEach((mod, mIdx) => {
                mod.sections.forEach((sec, sIdx) => {
                    let count = 0;
                    if (q) {
                        count = sec.rows.filter(row => {
                            return row.some(cell => String(cell).toLowerCase().includes(q));
                        }).length;
                    }
                    const badgeSpan = document.getElementById(`badge-${mIdx}-${sIdx}`);
                    if (badgeSpan) {
                        badgeSpan.innerText = count > 0 ? ` (${count})` : '';
                        badgeSpan.style.color = count > 0 ? 'var(--critical-color)' : '';
                    }
                });
            });
        }

        function sortTable(colIndex) {
            if (sortColIndex === colIndex) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColIndex = colIndex;
                sortDirection = 'asc';
            }
            applyFilterAndDraw();
        }

        function changePage(direction) {
            const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
            const newPage = currentPage + direction;
            if (newPage >= 1 && newPage <= totalPages) {
                currentPage = newPage;
                drawTable();
            }
        }

        function selectRow(index, trElement) {
            selectedRowIndex = index;
            document.querySelectorAll('#table-body tr').forEach(r => r.classList.remove('selected'));
            trElement.classList.add('selected');

            const mod = reportData.modules[activeModuleIndex];
            const sec = mod.sections[activeSectionIndex];
            const row = filteredRows[index];
            if (!sec || !row) return;

            const drawer = document.getElementById('details-drawer');
            const drawerTitle = document.getElementById('drawer-title');
            const drawerContent = document.getElementById('drawer-content');

            drawerTitle.innerText = sec.title + " Detail";
            drawerContent.innerHTML = "";

            sec.headers.forEach((h, idx) => {
                const label = h;
                const value = row[idx];
                
                const div = document.createElement('div');
                div.className = 'detail-row';
                
                let valHTML = `<div class="detail-value">${value}</div>`;
                if (label.toLowerCase().includes('recommendation') || label.toLowerCase().includes('suggested_action') || label.toLowerCase().includes('fix')) {
                    valHTML = `<div class="detail-value recommendation-box">${value}</div>`;
                }
                
                div.innerHTML = `
                    <div class="detail-label">${label}</div>
                    ${valHTML}
                `;
                drawerContent.appendChild(div);
            });

            drawer.classList.add('open');
        }

        function closeDrawer() {
            document.getElementById('details-drawer').classList.remove('open');
            document.querySelectorAll('#table-body tr').forEach(r => r.classList.remove('selected'));
            selectedRowIndex = -1;
        }

        function toggleFullscreen() {
            const container = document.getElementById('table-container');
            container.classList.toggle('fullscreen-active');
        }

        function exportData(format) {
            const mod = reportData.modules[activeModuleIndex];
            const sec = mod.sections[activeSectionIndex];
            if (!sec) return;

            if (format === 'copy') {
                const text = filteredRows.map(r => r.join('\\t')).join('\\n');
                navigator.clipboard.writeText(text);
                alert("Data copied to clipboard!");
            } else if (format === 'csv') {
                let csv = sec.headers.join(',') + '\\n';
                filteredRows.forEach(r => {
                    csv += r.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',') + '\\n';
                });
                downloadFile(csv, `${sec.id}_report.csv`, 'text/csv');
            } else if (format === 'json') {
                const expData = filteredRows.map(r => {
                    const obj = {};
                    sec.headers.forEach((h, idx) => obj[h] = r[idx]);
                    return obj;
                });
                downloadFile(JSON.stringify(expData, null, 2), `${sec.id}_report.json`, 'application/json');
            } else if (format === 'md') {
                let md = `| ${sec.headers.join(' | ')} |\\n`;
                md += `| ${sec.headers.map(() => '---').join(' | ')} |\\n`;
                filteredRows.forEach(r => {
                    md += `| ${r.join(' | ')} |\\n`;
                });
                downloadFile(md, `${sec.id}_report.md`, 'text/markdown');
            }
        }

        function downloadFile(content, fileName, contentType) {
            const blob = new Blob([content], { type: contentType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            a.click();
            URL.revokeObjectURL(url);
        }
    </script>
</body>
</html>
"""

def generate_unified_html_report(output_dir: Path):
    """
    Scans output_dir for module subdirectories, reads their JSON outputs,
    and aggregates them into a single file named index.html.
    """
    if not output_dir.exists():
        raise FileNotFoundError(f"Directory {output_dir} does not exist.")

    # 1. Resolve modules that exist inside output_dir
    module_subdirs = [
        ("Code Metrics", "01_metrics"),
        ("Security Checkers", "02_security"),
        ("Code Analysis", "03_Code_Analysis"),
        ("Contributor Analysis", "04_Contributor_Analysis"),
        ("Repository Intelligence", "05_Repository_Intelligence"),
        ("Knowledge Graph", "06_knowledge_graph")
    ]

    modules_payload = []
    global_summary_cards = []

    for mod_name, subdir_name in module_subdirs:
        subdir_path = output_dir / subdir_name
        if not subdir_path.exists():
            continue

        # Load all json files
        json_files = sorted(list(subdir_path.glob("*.json")), key=lambda x: x.name)
        sections = []
        for jf in json_files:
            section = json_file_to_section(jf)
            if section:
                sections.append(section)
                
                # Check for metrics
                if "summary" in jf.name or "health" in jf.name:
                    try:
                        data = json.loads(jf.read_text(encoding='utf-8'))
                        # Add overview
                        if "findings_summary" in data:
                            fs = data["findings_summary"]
                            for sev in ["critical", "high"]:
                                if fs.get(sev, 0) > 0:
                                    global_summary_cards.append({
                                        "title": f"{mod_name} - {sev.title()}",
                                        "value": str(fs[sev]),
                                        "class": "critical"
                                    })
                        if "repository_health" in data:
                            rh = data["repository_health"]
                            if "overall_score" in rh:
                                global_summary_cards.append({
                                    "title": "Health Score",
                                    "value": f"{rh['overall_score']:.1f}%",
                                    "class": "success" if rh['overall_score'] >= 80 else "warning"
                                })
                    except Exception:
                        pass

        if sections:
            modules_payload.append({
                "name": mod_name,
                "sections": sections
            })

    # Read general scan details (attempt to load from any scan metadata file)
    repo_name = output_dir.parent.name
    repo_path = "N/A"
    duration = "N/A"
    
    metadata_files = list(output_dir.glob("**/10_scan_metadata.json")) + list(output_dir.glob("**/08_scan_metadata.json"))
    if metadata_files:
        try:
            meta = json.loads(metadata_files[0].read_text(encoding='utf-8')).get('scan_metadata', {})
            repo_path = meta.get('repository_path', 'N/A')
            repo_name = Path(repo_path).name
            duration = f"{meta.get('scan_duration', 0.0):.4f} seconds"
        except Exception:
            pass

    payload = {
        "repo_name": repo_name,
        "repo_path": repo_path,
        "duration": duration,
        "summary_cards": global_summary_cards[:4], # limit to top 4 cards
        "modules": modules_payload
    }

    # Render unified report
    html_content = UNIFIED_TEMPLATE.replace("__PAYLOAD_JSON__", json.dumps(payload, indent=2))
    
    output_file = output_dir / "index.html"
    output_file.write_text(html_content, encoding='utf-8')
    return output_file
