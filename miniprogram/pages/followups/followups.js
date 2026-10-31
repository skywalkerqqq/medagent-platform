const api = require('../../utils/api');

Page({
  data: { loading: true, error: '', items: [], answer: '{"symptom":"无症状"}', result: null, submitting: false },
  onShow() { this.load(); },
  load() {
    this.setData({ loading: true, error: '' });
    api.ensureLogin()
      .then(() => api.request('/api/patient/followups'))
      .then((data) => this.setData({ loading: false, items: data.items || [] }))
      .catch((err) => this.setData({ loading: false, error: err.message }));
  },
  onInput(e) { this.setData({ answer: e.detail.value }); },
  submit() {
    const task = this.data.items[0];
    if (!task) { wx.showToast({ title: '暂无随访任务', icon: 'none' }); return; }
    let answers = {};
    try { answers = JSON.parse(this.data.answer); } catch (e) { answers = { symptom: this.data.answer }; }
    this.setData({ submitting: true, error: '' });
    api.request(`/api/patient/followups/${task.id}/submit`, { method: 'POST', data: { answers } })
      .then((result) => {
        this.setData({ submitting: false, result });
        wx.showToast({ title: result.risk_flag ? '已转人工' : '已提交', icon: 'none' });
      })
      .catch((err) => this.setData({ submitting: false, error: err.message }));
  },
});
