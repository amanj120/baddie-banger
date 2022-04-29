window.onload = function() {
    var c = document.getElementById("artist_graph");
    var ctx = c.getContext("2d");
    var img = new Image(40,40);

    img.source = "../images/Doja_Cat.jpg"
    ctx.drawImage(img, 100, 100);
    ctx.beginPath();
    ctx.arc(100, 75, 50, 0, 2 * Math.PI);
    ctx.stroke();
}; 