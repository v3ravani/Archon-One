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
            margin: 0;
            padding: 0;
        }

        /* Sidebar navigation */
        .sidebar {
            width: 280px;
            flex-shrink: 0;
            border-right: 1px solid var(--border-color);
            background-color: var(--card-color);
            display: flex;
            flex-direction: column;
            padding: 20px 0;
            height: 100vh;
            overflow: hidden;
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

        /* Main Workspace */
        .main-workspace {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            height: 100vh;
            position: relative;
            overflow: hidden;
            background-color: var(--bg-color);
        }

        /* Header block */
        .header {
            height: 70px;
            flex-shrink: 0;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 24px;
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
            height: calc(100vh - 70px);
            padding: 20px 24px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            gap: 16px;
            box-sizing: border-box;
        }

        /* Summary Cards Grid */
        .summary-grid {
            flex-shrink: 0;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
        }

        .summary-card {
            background-color: var(--card-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px 20px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }

        .summary-card-title {
            font-size: 0.75rem;
            color: #6c757d;
            font-weight: 600;
            text-transform: uppercase;
        }

        .summary-card-value {
            font-size: 1.5rem;
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
            flex-grow: 1;
            min-height: 0;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .table-card-header {
            flex-shrink: 0;
            padding: 12px 18px;
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
            flex-grow: 1;
            min-height: 0;
            overflow-y: auto;
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

        /* Diagram Viewer Styles */
        .diagram-container {
            display: none;
            flex-direction: column;
            gap: 20px;
            height: calc(100vh - 120px);
            overflow: hidden;
            width: 100%;
        }

        .diagram-workbench {
            display: flex;
            gap: 20px;
            flex-grow: 1;
            height: 100%;
            overflow: hidden;
        }

        .diagram-selector-panel {
            width: 280px;
            background-color: var(--card-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            flex-shrink: 0;
        }

        .diagram-search-box {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        .diagram-search-input {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 0.85rem;
        }

        .diagram-list {
            list-style: none;
            overflow-y: auto;
            flex-grow: 1;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .diagram-list-item {
            padding: 10px 12px;
            font-size: 0.85rem;
            font-weight: 500;
            border-radius: 6px;
            cursor: pointer;
            transition: background-color 0.2s;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .diagram-list-item:hover {
            background-color: var(--border-color);
        }

        .diagram-list-item.active {
            background-color: var(--primary-btn);
            color: var(--bg-color);
        }

        .diagram-viewer-panel {
            flex-grow: 1;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            position: relative;
        }

        .diagram-viewer-header {
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            background-color: var(--card-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .diagram-title-block h3 {
            font-size: 1.1rem;
            font-weight: bold;
        }

        .diagram-desc {
            font-size: 0.8rem;
            color: #6c757d;
            margin-top: 4px;
        }

        .diagram-toolbar {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        .diagram-viewport-wrapper {
            flex-grow: 1;
            overflow: hidden;
            position: relative;
            background-color: #fafafa;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .diagram-viewport {
            width: 100%;
            height: 100%;
            overflow: hidden;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: grab;
        }

        .diagram-viewport:active {
            cursor: grabbing;
        }

        .diagram-viewport svg {
            user-select: none;
            transform-origin: center center;
            transition: transform 0.05s ease-out;
        }

        .code-viewer {
            width: 100%;
            height: 100%;
            overflow: auto;
            padding: 20px;
            background-color: #1e1e1e;
            color: #d4d4d4;
            font-family: Consolas, Monaco, "Andale Mono", "Ubuntu Mono", monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            white-space: pre-wrap;
            display: none;
            margin: 0;
            border-radius: 0;
        }

        .btn-toggle-group {
            display: flex;
            border: 1px solid var(--primary-btn);
            border-radius: 6px;
            overflow: hidden;
        }

        .btn-toggle {
            padding: 6px 12px;
            font-size: 0.8rem;
            font-weight: 600;
            border: none;
            cursor: pointer;
            background-color: var(--bg-color);
            color: var(--primary-btn);
        }

        .btn-toggle.active {
            background-color: var(--primary-btn);
            color: var(--bg-color);
        }

        .diagram-fullscreen {
            position: fixed !important;
            top: 0;
            left: 0;
            width: 100vw !important;
            height: 100vh !important;
            z-index: 2000;
            background-color: white;
            padding: 20px;
            display: flex;
            flex-direction: column;
        }

        .diagram-fullscreen .diagram-viewport-wrapper {
            height: calc(100vh - 120px);
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
                        <button class="btn btn-secondary" id="btn-fullscreen" onclick="toggleFullscreen()">Fullscreen</button>
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
                <div class="pagination-container" style="display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap;">
                    <div class="pagination-info" id="pagination-info">Total: 0 entries</div>
                </div>
            </div>

            <!-- Diagram Workbench (Hidden by default) -->
            <div class="diagram-container" id="diagram-viewer-container">
                <div class="diagram-workbench">
                    <!-- Left Sidebar Selectors -->
                    <div class="diagram-selector-panel">
                        <div class="diagram-search-box">
                            <input type="text" id="diagram-search" class="diagram-search-input" placeholder="Search diagrams..." oninput="handleDiagramSearch(this.value)">
                        </div>
                        <ul class="diagram-list" id="diagram-list-items">
                            <!-- Populated dynamically -->
                        </ul>
                    </div>

                    <!-- Right Viewer Area -->
                    <div class="diagram-viewer-panel" id="diagram-viewport-panel">
                        <div class="diagram-viewer-header">
                            <div class="diagram-title-block">
                                <h3 id="active-diagram-title">Diagram Title</h3>
                                <p class="diagram-desc" id="active-diagram-desc">Description of this diagram...</p>
                            </div>
                            <div class="diagram-toolbar">
                                <div class="btn-toggle-group" style="margin-right: 15px;">
                                    <button class="btn-toggle active" id="btn-view-mermaid" onclick="setDiagramViewMode('mermaid')">Mermaid Render</button>
                                    <button class="btn-toggle" id="btn-view-plantuml" onclick="setDiagramViewMode('plantuml')">PlantUML Code</button>
                                </div>
                                <button class="btn btn-secondary" onclick="zoomDiagram(1.2)" id="btn-zoom-in" style="padding: 6px 10px;">＋</button>
                                <button class="btn btn-secondary" onclick="zoomDiagram(0.8)" id="btn-zoom-out" style="padding: 6px 10px;">－</button>
                                <button class="btn btn-secondary" onclick="resetZoom()" id="btn-zoom-reset">Reset</button>
                                <button class="btn btn-secondary" onclick="downloadActiveDiagram('source')">Source</button>
                                <button class="btn btn-secondary" onclick="downloadActiveDiagram('svg')" id="btn-download-svg">SVG</button>
                                <button class="btn btn-secondary" onclick="toggleDiagramFullscreen()">Fullscreen</button>
                            </div>
                        </div>

                        <div class="diagram-viewport-wrapper">
                            <div class="diagram-viewport" id="mermaid-render-area" onmousedown="startDiagramDrag(event)" onmousemove="dragDiagram(event)" onmouseup="endDiagramDrag()" onmouseleave="endDiagramDrag()">
                                <!-- Rendered Mermaid SVG here -->
                            </div>
                            <pre class="code-viewer" id="plantuml-code-area"><code id="plantuml-code-text">PlantUML source code...</code></pre>
                        </div>
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

            if (reportData.diagrams && reportData.diagrams.length > 0) {
                const li = document.createElement('li');
                li.className = 'nav-link';
                li.innerText = 'Architecture Diagrams';
                li.onclick = () => switchToDiagramsView(li);
                navContainer.appendChild(li);
                
                loadMermaidLibrary();
                populateDiagramsList();
                
                if (reportData.sections.length === 0) {
                    switchToDiagramsView(li);
                }
            }

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

            // Hide diagrams, restore table elements
            document.getElementById('diagram-viewer-container').style.display = 'none';
            document.getElementById('summary-cards').style.display = 'grid';
            document.getElementById('table-container').style.display = 'flex';
            document.getElementById('global-search').style.display = 'block';

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
                document.getElementById('pagination-info').innerText = "Total: 0 entries";
                return;
            }

            for (let i = 0; i < filteredRows.length; i++) {
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

            document.getElementById('pagination-info').innerText = `Total: ${filteredRows.length} entries`;
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
            const btn = document.getElementById('btn-fullscreen');
            const isFull = container.classList.toggle('fullscreen-active');
            if (btn) {
                btn.innerText = isFull ? "Exit Fullscreen" : "Fullscreen";
            }
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

        // Diagrams JavaScript logic
        let currentDiagramViewMode = 'mermaid';
        let activeDiagramId = 'architecture';
        let zoomScale = 1.0;
        let panX = 0;
        let panY = 0;
        let isDragging = false;
        let dragStartX = 0;
        let dragStartY = 0;

        function loadMermaidLibrary() {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
            script.onload = () => {
                mermaid.initialize({
                    startOnLoad: false,
                    theme: 'default',
                    flowchart: { useMaxWidth: false, htmlLabels: true },
                    securityLevel: 'loose'
                });
                renderActiveDiagram();
            };
            script.onerror = () => {
                console.warn("Failed to load Mermaid from CDN. Gracefully falling back to PlantUML source view.");
                document.getElementById('btn-view-mermaid').style.display = 'none';
                setDiagramViewMode('plantuml');
            };
            document.head.appendChild(script);
        }

        function populateDiagramsList() {
            const listContainer = document.getElementById('diagram-list-items');
            listContainer.innerHTML = "";
            
            const q = document.getElementById('diagram-search').value.toLowerCase();
            const filtered = reportData.diagrams.filter(d => 
                d.title.toLowerCase().includes(q) || d.description.toLowerCase().includes(q)
            );
            
            filtered.forEach(d => {
                const li = document.createElement('li');
                li.className = 'diagram-list-item' + (d.id === activeDiagramId ? ' active' : '');
                li.innerText = d.title;
                li.onclick = () => selectDiagram(d.id, li);
                listContainer.appendChild(li);
            });
        }

        function selectDiagram(id, liElement) {
            activeDiagramId = id;
            document.querySelectorAll('.diagram-list-item').forEach(l => l.classList.remove('active'));
            liElement.classList.add('active');
            
            const diag = reportData.diagrams.find(d => d.id === id);
            if (!diag) return;
            
            document.getElementById('active-diagram-title').innerText = diag.title;
            document.getElementById('active-diagram-desc').innerText = diag.description;
            
            resetZoom();
            renderActiveDiagram();
        }

        function setDiagramViewMode(mode) {
            currentDiagramViewMode = mode;
            document.getElementById('btn-view-mermaid').classList.toggle('active', mode === 'mermaid');
            document.getElementById('btn-view-plantuml').classList.toggle('active', mode === 'plantuml');
            
            const renderArea = document.getElementById('mermaid-render-area');
            const codeArea = document.getElementById('plantuml-code-area');
            const zoomInBtn = document.getElementById('btn-zoom-in');
            const zoomOutBtn = document.getElementById('btn-zoom-out');
            const zoomResetBtn = document.getElementById('btn-zoom-reset');
            const downloadSvgBtn = document.getElementById('btn-download-svg');
            
            if (mode === 'mermaid') {
                renderArea.style.display = 'flex';
                codeArea.style.display = 'none';
                zoomInBtn.style.display = 'inline-flex';
                zoomOutBtn.style.display = 'inline-flex';
                zoomResetBtn.style.display = 'inline-flex';
                downloadSvgBtn.style.display = 'inline-flex';
            } else {
                renderArea.style.display = 'none';
                codeArea.style.display = 'block';
                zoomInBtn.style.display = 'none';
                zoomOutBtn.style.display = 'none';
                zoomResetBtn.style.display = 'none';
                downloadSvgBtn.style.display = 'none';
            }
            renderActiveDiagram();
        }

        function renderActiveDiagram() {
            const diag = reportData.diagrams.find(d => d.id === activeDiagramId);
            if (!diag) return;
            
            if (currentDiagramViewMode === 'mermaid') {
                const renderArea = document.getElementById('mermaid-render-area');
                renderArea.innerHTML = `<div style="color:#6c757d; font-size:0.9rem; padding:20px;">Rendering diagram...</div>`;
                
                if (typeof mermaid !== 'undefined') {
                    try {
                        const uniqueId = `mermaid_svg_${diag.id}_${Date.now()}`;
                        mermaid.render(uniqueId, diag.mermaid).then(({ svg }) => {
                            renderArea.innerHTML = svg;
                            const svgElement = renderArea.querySelector('svg');
                            if (svgElement) {
                                svgElement.style.maxWidth = '100%';
                                svgElement.style.height = 'auto';
                                svgElement.style.transformOrigin = 'center center';
                                applyTransform();
                            }
                        }).catch(err => {
                            renderArea.innerHTML = `<div style="color:var(--critical-color); font-size:0.85rem; padding:20px; text-align:left; word-break:break-word;">
                                <strong>Failed to render Mermaid diagram automatically:</strong><br>${err}
                                <br><br>You can switch to the <em>PlantUML Code</em> view or download the Mermaid source code to render it in an external viewer.
                            </div>`;
                        });
                    } catch (e) {
                        renderArea.innerHTML = `<div style="color:var(--critical-color);">Render error: ${e}</div>`;
                    }
                } else {
                    renderArea.innerHTML = `<div style="color:#6c757d; font-size:0.9rem; padding:20px;">Mermaid library loading...</div>`;
                }
            } else {
                const codeText = document.getElementById('plantuml-code-text');
                codeText.innerText = diag.plantuml;
            }
        }

        function zoomDiagram(factor) {
            zoomScale *= factor;
            if (zoomScale < 0.2) zoomScale = 0.2;
            if (zoomScale > 5.0) zoomScale = 5.0;
            applyTransform();
        }

        function resetZoom() {
            zoomScale = 1.0;
            panX = 0;
            panY = 0;
            applyTransform();
        }

        function applyTransform() {
            const svg = document.querySelector('#mermaid-render-area svg');
            if (svg) {
                svg.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomScale})`;
            }
        }

        function startDiagramDrag(e) {
            if (currentDiagramViewMode !== 'mermaid') return;
            isDragging = true;
            dragStartX = e.clientX - panX;
            dragStartY = e.clientY - panY;
            e.preventDefault();
        }

        function dragDiagram(e) {
            if (!isDragging) return;
            panX = e.clientX - dragStartX;
            panY = e.clientY - dragStartY;
            applyTransform();
        }

        function endDiagramDrag() {
            isDragging = false;
        }

        function toggleDiagramFullscreen() {
            const panel = document.getElementById('diagram-viewport-panel');
            panel.classList.toggle('diagram-fullscreen');
            resetZoom();
        }

        function downloadActiveDiagram(type) {
            const diag = reportData.diagrams.find(d => d.id === activeDiagramId);
            if (!diag) return;
            
            if (type === 'source') {
                if (currentDiagramViewMode === 'mermaid') {
                    downloadFile(diag.mermaid, `${diag.id}.mmd`, 'text/plain');
                } else {
                    downloadFile(diag.plantuml, `${diag.id}.puml`, 'text/plain');
                }
            } else if (type === 'svg') {
                const svgWrapper = document.getElementById('mermaid-render-area');
                const svg = svgWrapper.querySelector('svg');
                if (svg) {
                    const svgContent = svg.outerHTML;
                    downloadFile(svgContent, `${diag.id}.svg`, 'image/svg+xml');
                } else {
                    alert("No rendered SVG available to download. Render in Mermaid mode first.");
                }
            }
        }

        function switchToDiagramsView(navElement) {
            closeDrawer();
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            navElement.classList.add('active');
            
            document.getElementById('summary-cards').style.display = 'none';
            document.getElementById('table-container').style.display = 'none';
            document.getElementById('global-search').style.display = 'none';
            document.getElementById('diagram-viewer-container').style.display = 'flex';
            
            document.getElementById('section-title').innerText = "Architecture Diagrams";
            
            renderActiveDiagram();
        }

        function handleDiagramSearch(val) {
            populateDiagramsList();
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
            "sections": formatted_sections,
            "diagrams": data.get("diagrams", [])
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
    diagrams = []
    
    # Process each JSON file
    for jf in json_files:
        if jf.name == "11_architecture_diagrams.json":
            try:
                diagrams_data = json.loads(jf.read_text(encoding='utf-8'))
                diagrams = diagrams_data.get("diagrams", [])
            except Exception:
                pass
            continue
            
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
        "sections": sections,
        "diagrams": diagrams
    }
    
    generate_html_report(output_root / "report.html", data)
