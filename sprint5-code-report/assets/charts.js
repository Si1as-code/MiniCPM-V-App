(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart: Test Coverage ---
  var chartCov = echarts.init(document.getElementById('chart-coverage'), null, { renderer: 'svg' });
  chartCov.setOption({
    animation: false,
    tooltip: { trigger: 'item', appendToBody: true, backgroundColor: bg2, borderColor: rule, textStyle: { color: ink } },
    legend: { bottom: 0, textStyle: { color: muted }, data: ['量化', 'ONNX导出', 'Benchmark', '回归测试', '发布', '流水线', '集成'] },
    color: [accent, accent2, '#a78bfa', '#34d399', '#f472b6', '#fb923c', accent + '99'],
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['50%', '48%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: bg2, borderWidth: 2 },
      label: { color: muted, fontSize: 12 },
      emphasis: { label: { fontSize: 16, fontWeight: 'bold' } },
      data: [
        { value: 7, name: '量化' },
        { value: 3, name: 'ONNX导出' },
        { value: 6, name: 'Benchmark' },
        { value: 7, name: '回归测试' },
        { value: 6, name: '发布' },
        { value: 8, name: '流水线' },
        { value: 2, name: '集成' }
      ]
    }]
  });
  window.addEventListener('resize', function() { chartCov.resize(); });
})();