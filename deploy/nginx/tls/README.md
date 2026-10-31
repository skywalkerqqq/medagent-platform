# TLS 证书目录（不要提交真实证书/私钥）
# 本地联调可生成自签证书：
#   openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
#     -keyout server.key -out server.crt -subj "/CN=localhost"
# 生产必须使用院方 CA 或公网 CA 签发的证书，并限制目录权限 600。
