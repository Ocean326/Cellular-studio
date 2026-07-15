(function initTrajectoryStudioDeploymentConfig() {
	window.TrajectoryStudioDeploymentConfig = {
  "defaultTileMode": "online",
  "tilePresets": {
    "online": {
      "label": "在线",
      "description": "公网高德在线底图"
    },
    "offline": {
      "label": "离线",
      "description": "容器内离线瓦片服务",
      "minZoom": 3,
      "maxNativeZoom": 16,
      "maxZoom": 18
    },
    "intranet": {
      "label": "内网",
      "description": "接入内网瓦片服务",
      "url": "http://192.110.14.224:8077/styles/basic/{z}/{x}/{y}.png",
      "attribution": "© Map data © OpenStreetMap contributors | Tiles © MapTiler",
      "coordinateSystem": "wgs84",
      "minZoom": 3,
      "maxNativeZoom": 19,
      "maxZoom": 19,
      "detectRetina": true
    }
  }
};
})();
