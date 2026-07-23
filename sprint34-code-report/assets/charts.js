(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();

  // --- Chart: Test Coverage Distribution ---
  var chart1 = echarts.init(document.getElementById('chart-test-coverage'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: { trigger: 'item', appendToBody: true },
    legend: { bottom: '5%', left: 'center', textStyle: { color: muted } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, color: ink, formatter: '{b}\n{c} 项' },
      labelLine: { lineStyle: { color: muted } },
      data: [
        { value: 9, name: 'Sprint 3: API 调度', itemStyle: { color: accent } },
        { value: 13, name: 'Sprint 4: 后台服务', itemStyle: { color: accent2 } },
      ]
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });
})();
