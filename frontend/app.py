from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def login():
    return render_template("index.html")

@app.route("/captcha")
def captcha():
    return render_template("captcha.html")

if __name__ == "__main__":
    app.run(debug=True)