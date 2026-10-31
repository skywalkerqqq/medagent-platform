const api = require('../../utils/api');

Page({
  data: { loading: true, error: '', items: [] },
  onShow() { this.load(); },
  load() {
    this.setData({ loading: true, error: '' });
    api.ensureLogin()
      .then(() => api.request('/api/patient/reports'))
      .then((data) => this.setData({ loading: false, items: data.items || [] }))
      .catch((err) => this.setData({ loading: false, error: err.message }));
  },
});
