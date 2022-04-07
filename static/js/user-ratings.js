window.onload = function() {
  var c = document.getElementById("artist_graph");
  var ctx = c.getContext("2d");
  var img = document.getElementById("scream");
  ctx.drawImage(img, 10, 10);
}; 