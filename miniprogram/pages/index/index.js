const api = require('../../utils/api');

Page({
  data: { loading: true, bound: false, nameMask: '', consent: [], error: '' },
  onShow() {
    this.load();
  },
  load() {
    this.setData({ loading: true, error: '' });
    api.ensureLogin()
      .then(() => api.request('/api/patient/me'))
      .then((me) => {
        this.setData({
          loading: false,
          bound: !!me.bound,
          nameMask: me.name_mask || '',
          consent: me.consent || [],
          reports: me.reports || 0,
          tasks: me.tasks || 0,
        });
      })
      .catch((err) => this.setData({ loading: false, error: err.message }));
  },
  goBind() { wx.navigateTo({ url: '/pages/bind/bind' }); },
  goReports() { wx.navigateTo({ url: '/pages/reports/reports' }); },
  goFollowups() { wx.navigateTo({ url: '/pages/followups/followups' }); },
});
