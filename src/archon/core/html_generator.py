import json
from pathlib import Path
from typing import Dict, Any, List

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Archon One Report - __MODULE_NAME__</title>
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
            width: 280px;
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
            gap: 4px;
            padding: 15px;
            overflow-y: auto;
            flex-grow: 1;
        }

        .nav-link {
            padding: 10px 15px;
            text-decoration: none;
            color: var(--text-color);
            border-radius: 6px;
            font-weight: 500;
            font-size: 0.9rem;
            cursor: pointer;
            transition: background-color 0.2s;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .nav-link:hover {
            background-color: var(--border-color);
        }

        .nav-link.active {
            background-color: var(--primary-btn);
            color: var(--bg-color);
        }

        .nav-footer {
            padding: 15px;
            border-top: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            gap: 8px;
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
            width: 250px;
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

        .btn-nav {
            width: 100%;
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
            <span>Interactive Report</span>
        </div>
        <ul class="nav-links" id="sections-nav">
            <!-- Populated dynamically via JS -->
        </ul>
        <div class="nav-footer">
            <a href="#" id="btn-prev-mod" class="btn btn-secondary btn-nav">← Previous Module</a>
            <a href="#" id="btn-next-mod" class="btn btn-secondary btn-nav">Next Module →</a>
        </div>
    </div>

    <!-- Main Workspace -->
    <div class="main-workspace">
        <!-- Header -->
        <div class="header">
            <div class="header-info">
                <h2 id="header-module-name">Module Name</h2>
                <p id="header-repo-details">Repository: Name | Date: Timestamp</p>
            </div>
            <div class="header-actions">
                <input type="text" id="global-search" class="search-box" placeholder="Search this section..." oninput="handleSearch(this.value)">
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
        let activeSectionId = "";
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
            // Render Header Info
            document.getElementById('header-module-name').innerText = reportData.module_name;
            document.getElementById('header-repo-details').innerText = `Repository: ${reportData.repo_name} | Path: ${reportData.repo_path} | Scan Duration: ${reportData.duration}`;
            
            // Set up Module navigation links
            const prevBtn = document.getElementById('btn-prev-mod');
            const nextBtn = document.getElementById('btn-next-mod');
            if (reportData.navigation && reportData.navigation.prev) {
                prevBtn.href = reportData.navigation.prev;
                prevBtn.style.display = 'inline-flex';
            } else {
                prevBtn.style.display = 'none';
            }
            if (reportData.navigation && reportData.navigation.next) {
                nextBtn.href = reportData.navigation.next;
                nextBtn.style.display = 'inline-flex';
            } else {
                nextBtn.style.display = 'none';
            }

            // Populated navigation sections
            const navContainer = document.getElementById('sections-nav');
            navContainer.innerHTML = "";
            reportData.sections.forEach((sec, idx) => {
                const li = document.createElement('li');
                li.className = 'nav-link' + (idx === 0 ? ' active' : '');
                li.innerText = sec.title;
                li.onclick = () => switchSection(sec.id, li);
                navContainer.appendChild(li);
            });

            if (reportData.sections.length > 0) {
                switchSection(reportData.sections[0].id);
            }
        }

        function switchSection(sectionId, navElement = null) {
            activeSectionId = sectionId;
            currentPage = 1;
            searchQuery = "";
            document.getElementById('global-search').value = "";
            sortColIndex = -1;
            sortDirection = 'asc';
            selectedRowIndex = -1;
            closeDrawer();

            // Handle active class toggling
            if (navElement) {
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                navElement.classList.add('active');
            }

            const sec = reportData.sections.find(s => s.id === sectionId);
            if (!sec) return;

            // Render Title & Description
            document.getElementById('section-title').innerText = sec.title;
            
            // Render Section Summary Cards if they exist
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

            // Filter and Draw rows
            applyFilterAndDraw();
        }

        function applyFilterAndDraw() {
            const sec = reportData.sections.find(s => s.id === activeSectionId);
            if (!sec) return;

            if (!searchQuery) {
                filteredRows = [...sec.rows];
            } else {
                const q = searchQuery.toLowerCase();
                filteredRows = sec.rows.filter(row => {
                    return row.some(cell => String(cell).toLowerCase().includes(q));
                });
            }

            // Apply Sort
            if (sortColIndex !== -1) {
                filteredRows.sort((a, b) => {
                    let valA = a[sortColIndex];
                    let valB = b[sortColIndex];
                    
                    // Attempt numerical sort
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
                const sec = reportData.sections.find(s => s.id === activeSectionId);
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

            const sec = reportData.sections.find(s => s.id === activeSectionId);
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
            const sec = reportData.sections.find(s => s.id === activeSectionId);
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

def json_file_to_section(file_path: Path) -> Dict[str, Any]:
    name_clean = file_path.stem.replace('_', ' ').title()
    if name_clean[0:2].isdigit() and name_clean[2] == ' ':
        name_clean = name_clean[3:]
    try:
        content = json.loads(file_path.read_text(encoding='utf-8'))
    except Exception:
        return None
        
    headers = []
    rows = []
    
    # Check if content is a list of objects
    if isinstance(content, list):
        if len(content) > 0 and isinstance(content[0], dict):
            headers = list(content[0].keys())
            for item in content:
                rows.append([item.get(h, "") for h in headers])
        else:
            headers = ["Items"]
            rows = [[str(x)] for x in content]
            
    # Check if content is a dictionary
    elif isinstance(content, dict):
        # Look for a list value in the dict
        list_key = None
        for k, v in content.items():
            if isinstance(v, list):
                list_key = k
                break
                
        if list_key:
            list_val = content[list_key]
            if len(list_val) > 0 and isinstance(list_val[0], dict):
                headers = list(list_val[0].keys())
                for item in list_val:
                    rows.append([item.get(h, "") for h in headers])
            else:
                headers = [list_key.replace('_', ' ').title()]
                rows = [[str(x)] for x in list_val]
        else:
            # Flatten dictionary to a key-value list
            headers = ["Metric", "Value"]
            for k, v in content.items():
                if isinstance(v, dict):
                    for nk, nv in v.items():
                        rows.append([f"{k} - {nk}".replace('_', ' ').title(), str(nv)])
                else:
                    rows.append([k.replace('_', ' ').title(), str(v)])
                    
    display_headers = [h.replace('_', ' ').title() for h in headers]
    
    return {
        "id": file_path.stem,
        "title": name_clean,
        "headers": display_headers,
        "rows": rows
    }

def generate_html_report(output_path: Path, data: Dict[str, Any]):
    """
    Generates a premium offline-first standalone HTML report at output_path.
    """
    try:
        # Safeguard row values to strings to prevent script crashes on other data types
        formatted_sections = []
        for sec in data.get("sections", []):
            formatted_rows = []
            for r in sec.get("rows", []):
                formatted_rows.append([str(cell) for cell in r])
            
            formatted_sections.append({
                "id": sec.get("id"),
                "title": sec.get("title"),
                "description": sec.get("description", ""),
                "summary_cards": sec.get("summary_cards", []),
                "headers": sec.get("headers", []),
                "rows": formatted_rows
            })
            
        payload = {
            "module_name": data.get("module_name", "Archon One Module"),
            "repo_name": data.get("repo_name", "Unknown Repository"),
            "repo_path": data.get("repo_path", "N/A"),
            "duration": data.get("duration", "0.00 seconds"),
            "navigation": data.get("navigation", {}),
            "summary_cards": data.get("summary_cards", []),
            "sections": formatted_sections
        }
        
        # Serialize payload
        payload_str = json.dumps(payload, indent=2)
        
        # Render HTML content
        html_content = HTML_TEMPLATE.replace("__MODULE_NAME__", data.get("module_name", ""))
        html_content = html_content.replace("__PAYLOAD_JSON__", payload_str)
        
        # Write file
        output_path.write_text(html_content, encoding='utf-8')
    except Exception as e:
        # Fallback to write an error HTML file to avoid crashing the runner
        err_content = f"<html><body><h1>Failed to generate interactive HTML report</h1><p>{str(e)}</p></body></html>"
        try:
            output_path.write_text(err_content, encoding='utf-8')
        except Exception:
            pass

def compile_and_write_html_report(output_root: Path, results: Dict[str, Any], module_name: str, nav: Dict[str, str]):
    # Read all JSON files in output_root
    json_files = sorted(list(output_root.glob("*.json")), key=lambda x: x.name)
    sections = []
    summary_cards = []
    
    # Process each JSON file
    for jf in json_files:
        section = json_file_to_section(jf)
        if section:
            sections.append(section)
            
            # Extract summary cards from summary file
            if "summary" in jf.name:
                try:
                    data = json.loads(jf.read_text(encoding='utf-8'))
                    
                    # 1. Check overview metrics
                    if "repository_overview" in data:
                        ro = data["repository_overview"]
                        if "total_files" in ro:
                            summary_cards.append({"title": "Total Files", "value": str(ro["total_files"])})
                        if "supported_files" in ro:
                            summary_cards.append({"title": "Scanned Files", "value": str(ro["supported_files"])})
                            
                    # 2. Check findings counts
                    if "findings_summary" in data:
                        fs = data["findings_summary"]
                        for sev in ["critical", "high", "medium", "low"]:
                            if sev in fs:
                                summary_cards.append({
                                    "title": f"{sev.title()} Issues",
                                    "value": str(fs[sev]),
                                    "class": "critical" if sev in ["critical", "high"] else "warning"
                                })
                                
                    # 3. Check health rating
                    if "repository_health" in data:
                        rh = data["repository_health"]
                        if "overall_score" in rh:
                            summary_cards.append({
                                "title": "Health Score",
                                "value": f"{rh['overall_score']:.1f}%",
                                "class": "success" if rh['overall_score'] >= 80 else "warning"
                            })
                except Exception:
                    pass
                    
    # Format global metadata
    repo_path = Path(results.get('root_path', '.'))
    data = {
        "module_name": module_name,
        "repo_name": repo_path.name,
        "repo_path": str(repo_path),
        "duration": f"{results.get('scan_duration', 0.0):.4f} seconds",
        "navigation": nav,
        "summary_cards": summary_cards,
        "sections": sections
    }
    
    generate_html_report(output_root / "report.html", data)
