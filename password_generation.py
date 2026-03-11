from werkzeug.security import generate_password_hash
new_pass = "12345"
print(generate_password_hash(new_pass))