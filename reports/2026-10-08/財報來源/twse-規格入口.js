window.onload = function() {
  
      
      //<editor-fold desc="Changeable Configuration Block">
      window.ui = SwaggerUIBundle({
        "dom_id": "#swagger-ui",
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout",
        queryConfigEnabled: false,
        requestInterceptor: function(req) { req.headers['If-Modified-Since'] = 'Mon, 26 Jul 1997 05:00:00 GMT'; req.headers['Cache-Control'] = 'no-cache'; req.headers['Pragma'] = 'no-cache'; return req; },
        url: "https://openapi.twse.com.tw/v1/swagger.json",
      })
      
      //</editor-fold>


};
