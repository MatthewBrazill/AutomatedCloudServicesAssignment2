"use strict"

//Imports
const express = require("express");
const router = express.Router();

//Router Setup
router.get("/index", function (req, res) {
    res.render("index", {
        title: "Example Page",
        img_link: "",
        instance_ip: "",
        instance_type: "",
        public_ip: ""
    })
});

router.get("/monitoring", function (req, res) {
    res.render("monitoring", {
        title: "WebServer Monitoring",
        img_link: "",
        instance_ip: "",
        instance_type: "",
        public_ip: ""
    })
});

module.exports = router