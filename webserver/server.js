var http = require("http");
var server = http.createServer(function (req, res) {
    switch (req.url) {
        case "/index": res.write("<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Example Page</title></head><body><h1>Example Page</h1></body></html>")
        case "/monitoring": res.write("<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Monitoring</title></head><body><h1>Monitoring</h1></body></html>")
    }
})