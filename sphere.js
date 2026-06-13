// Rotating 3D tag sphere for the hero. No dependencies.
(function () {
  var root = document.querySelector('.sphere');
  if (!root) return;
  var tags = Array.prototype.slice.call(root.querySelectorAll('a'));
  var N = tags.length;
  if (!N) return;

  // Fibonacci sphere distribution
  var pts = [];
  for (var i = 0; i < N; i++) {
    var phi = Math.acos(-1 + (2 * i + 1) / N);
    var theta = Math.sqrt(N * Math.PI) * phi;
    pts.push({
      x: Math.cos(theta) * Math.sin(phi),
      y: Math.sin(theta) * Math.sin(phi),
      z: Math.cos(phi)
    });
  }

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var baseX = reduce ? 0 : 0.0022;
  var baseY = reduce ? 0 : 0.0040;
  var mx = 0, my = 0, hovering = false;

  root.addEventListener('mousemove', function (e) {
    var r = root.getBoundingClientRect();
    mx = (e.clientX - (r.left + r.width / 2)) / r.width;
    my = (e.clientY - (r.top + r.height / 2)) / r.height;
    hovering = true;
  });
  root.addEventListener('mouseleave', function () { hovering = false; });

  function radius() { return Math.min(root.clientWidth, root.clientHeight) / 2 - 26; }

  function frame() {
    var rotY = hovering ? mx * 0.05 : baseY;
    var rotX = hovering ? -my * 0.05 : baseX;
    var cy = Math.cos(rotY), siny = Math.sin(rotY);
    var cx = Math.cos(rotX), sinx = Math.sin(rotX);
    for (var i = 0; i < N; i++) {
      var p = pts[i];
      var x = p.x * cy - p.z * siny;
      var z = p.x * siny + p.z * cy;
      p.x = x; p.z = z;
      var y = p.y * cx - p.z * sinx;
      z = p.y * sinx + p.z * cx;
      p.y = y; p.z = z;
    }
    var R = radius();
    for (var j = 0; j < N; j++) {
      var q = pts[j], el = tags[j];
      var scale = (q.z + 2) / 3;            // [-1,1] -> [0.33,1]
      var px = q.x * R, py = q.y * R;
      el.style.transform = 'translate(-50%,-50%) translate(' + px.toFixed(1) + 'px,' + py.toFixed(1) + 'px) scale(' + scale.toFixed(3) + ')';
      el.style.opacity = ((q.z + 1.5) / 2.5).toFixed(3);
      el.style.zIndex = Math.round(scale * 100);
    }
    requestAnimationFrame(frame);
  }
  frame();
})();
