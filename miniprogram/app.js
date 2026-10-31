const api = require('./utils/api');

App({
  globalData: { user: null, ready: false },
  onLaunch() {
    api.login()
      .then((data) => {
        this.globalData.user = data.user;
        this.globalData.ready = true;
      })
      .catch(() => {
        this.globalData.ready = true;
      });
  },
});
