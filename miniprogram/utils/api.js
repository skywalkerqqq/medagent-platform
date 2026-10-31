const { BASE_URL } = require('../config');

const TOKEN_KEY = 'medagent_token';

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || '';
}

function request(path, options = {}) {
  const header = Object.assign({ 'Content-Type': 'application/json' }, options.header || {});
  const token = getToken();
  if (token) header.Authorization = `Bearer ${token}`;
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data,
      header,
      timeout: 15000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        const error = (res.data && res.data.error) || {};
        const err = new Error(error.message || `请求失败（HTTP ${res.statusCode}）`);
        err.code = error.code || `http_${res.statusCode}`;
        if (res.statusCode === 401) wx.removeStorageSync(TOKEN_KEY);
        reject(err);
      },
      fail(err) {
        reject(new Error(`网络错误：${err.errMsg || '无法连接中台'}`));
      },
    });
  });
}

function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (!res.code) {
          reject(new Error('wx.login 未返回 code'));
          return;
        }
        request('/api/auth/wx-login', { method: 'POST', data: { code: res.code } })
          .then((data) => {
            wx.setStorageSync(TOKEN_KEY, data.token);
            resolve(data);
          })
          .catch(reject);
      },
      fail(err) {
        reject(new Error(`wx.login 失败：${err.errMsg || ''}`));
      },
    });
  });
}

function ensureLogin() {
  if (getToken()) return Promise.resolve({ cached: true });
  return login();
}

module.exports = { BASE_URL, request, login, ensureLogin, getToken };
