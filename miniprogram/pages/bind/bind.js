const api = require('../../utils/api');

Page({
  data: { patientRef: 'P0001', verifyCode: '654321', loading: false, error: '', result: null },
  onInputRef(e) { this.setData({ patientRef: e.detail.value }); },
  onInputCode(e) { this.setData({ verifyCode: e.detail.value }); },
  submit() {
    this.setData({ loading: true, error: '' });
    api.ensureLogin()
      .then(() => api.request('/api/patient/bind', {
        method: 'POST',
        data: { patient_ref: this.data.patientRef.trim(), verify_code: this.data.verifyCode.trim() },
      }))
      .then((data) => {
        this.setData({ loading: false, result: data });
        wx.showToast({ title: '绑定成功', icon: 'success' });
        setTimeout(() => wx.navigateBack(), 800);
      })
      .catch((err) => this.setData({ loading: false, error: err.message }));
  },
});
