/* ============================================================
   PREDICTIVE HISTORY AUDIT — Client-side interactivity
   ============================================================ */

/* --- Radar Chart (using Chart.js) --- */
function initRadarChart(canvasId, scores) {
  const labels = [
    'Accuracy', 'Rigor', 'Framing',
    'Diversity', 'Normative', 'Determinism', 'Civ. Framing'
  ];
  const data = [
    scores.historical_accuracy,
    scores.argumentative_rigor,
    scores.framing_and_selectivity,
    scores.perspective_diversity,
    scores.normative_loading,
    scores.determinism_vs_contingency,
    scores.civilizational_framing
  ];

  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: 'rgba(255, 233, 160, 0.08)',
        borderColor: 'rgba(255, 233, 160, 0.6)',
        borderWidth: 1.5,
        pointBackgroundColor: function(context) {
          const v = context.raw;
          const colors = {
            1: '#ffcccc', 2: '#ffe2b0', 3: '#fff4a6',
            4: '#c6ffb0', 5: '#a6ffd8'
          };
          return colors[v] || '#c8c2b8';
        },
        pointBorderColor: 'transparent',
        pointRadius: 5,
        pointHoverRadius: 7,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        r: {
          min: 0,
          max: 5,
          ticks: {
            stepSize: 1,
            display: false,
          },
          grid: {
            color: 'rgba(255,255,255,0.06)',
          },
          angleLines: {
            color: 'rgba(255,255,255,0.06)',
          },
          pointLabels: {
            color: '#e5e0d8',
            font: {
              family: "'DM Sans', sans-serif",
              size: 11,
              weight: 500,
            }
          }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#171b22',
          borderColor: '#252a33',
          borderWidth: 1,
          titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
          bodyFont: { family: "'DM Sans', sans-serif", size: 12 },
          callbacks: {
            label: function(context) {
              return context.raw + ' / 5';
            }
          }
        }
      }
    }
  });
}

/* --- Table Sorting --- */
function initTableSort() {
  const table = document.querySelector('.data-table');
  if (!table) return;

  const headers = table.querySelectorAll('th[data-sort]');
  let currentSort = null;
  let currentDir = 'asc';

  // Detect pre-set default sort from markup
  headers.forEach(th => {
    if (th.classList.contains('sort-asc')) {
      currentSort = th.dataset.sort;
      currentDir = 'asc';
    } else if (th.classList.contains('sort-desc')) {
      currentSort = th.dataset.sort;
      currentDir = 'desc';
    }
  });

  function sortBy(key, type, dir) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort((a, b) => {
      let va = a.querySelector(`[data-value="${key}"]`)?.dataset.raw || a.querySelector(`[data-value="${key}"]`)?.textContent || '';
      let vb = b.querySelector(`[data-value="${key}"]`)?.dataset.raw || b.querySelector(`[data-value="${key}"]`)?.textContent || '';

      if (type === 'number') {
        va = parseFloat(va) || 0;
        vb = parseFloat(vb) || 0;
      }

      let cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return dir === 'asc' ? cmp : -cmp;
    });

    rows.forEach(row => tbody.appendChild(row));
  }

  headers.forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      const type = th.dataset.sortType || 'number';

      if (currentSort === key) {
        currentDir = currentDir === 'asc' ? 'desc' : 'asc';
      } else {
        currentSort = key;
        currentDir = type === 'string' ? 'asc' : 'desc';
      }

      headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(currentDir === 'asc' ? 'sort-asc' : 'sort-desc');

      sortBy(key, type, currentDir);
    });
  });
}

/* --- Series Filter --- */
function initSeriesFilter() {
  const tabs = document.querySelectorAll('.filter-tab[data-series]');
  const rows = document.querySelectorAll('.data-table tbody tr');

  if (!tabs.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const series = tab.dataset.series;
      rows.forEach(row => {
        if (series === 'all' || row.dataset.series === series) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      });
    });
  });
}

/* --- Collapsible Sections --- */
function initCollapsibles() {
  document.querySelectorAll('.section-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const target = document.getElementById(toggle.dataset.target);
      const isOpen = toggle.classList.contains('open');

      toggle.classList.toggle('open');
      if (target) target.classList.toggle('open');
    });
  });
}

/* --- Score Row Expand --- */
function initScoreExpand() {
  document.querySelectorAll('.score-row[data-expandable]').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => {
      row.classList.toggle('expanded');
      const hint = row.querySelector('.score-expand-hint');
      if (hint) {
        hint.innerHTML = row.classList.contains('expanded') ? '&#x25BE; Collapse' : '&#x25B8; Expand';
      }
    });
  });
}

/* --- Prediction/Claim Filter --- */
function initPredFilter() {
  const typeBar = document.getElementById('pred-filter-bar');
  const statusBar = document.getElementById('status-filter-bar');
  if (!typeBar) return;

  const typeTabs = typeBar.querySelectorAll('.filter-tab');
  const statusTabs = statusBar ? statusBar.querySelectorAll('.filter-tab') : [];
  const entries = document.querySelectorAll('.prediction-entry[data-pred-type]');
  const statsBars = document.querySelectorAll('.pred-stats');

  let activeType = 'all';
  let activeStatus = 'all';

  function applyFilters() {
    entries.forEach(entry => {
      const typeMatch = activeType === 'all' || entry.dataset.predType === activeType;
      const statusMatch = activeStatus === 'all' || entry.dataset.predStatus === activeStatus;
      entry.style.display = (typeMatch && statusMatch) ? '' : 'none';
    });

    statsBars.forEach(sb => {
      if (activeType === 'all') {
        sb.style.display = sb.dataset.predStats === 'prediction' ? '' : 'none';
      } else {
        sb.style.display = sb.dataset.predStats === activeType ? '' : 'none';
      }
    });
  }

  typeTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      typeTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeType = tab.dataset.predFilter;
      applyFilters();
    });
  });

  statusTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      statusTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeStatus = tab.dataset.statusFilter;
      applyFilters();
    });
  });
}

/* --- Init all --- */
document.addEventListener('DOMContentLoaded', () => {
  initTableSort();
  initSeriesFilter();
  initCollapsibles();
  initScoreExpand();
  initPredFilter();
});
