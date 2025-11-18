### **1. Automatically generate a screen grid**

The program divides your screen into 5×5, 6×6, 8×8, etc. grids and calculates the center coordinates of each grid cell.

---

### **2. Automatically move the mouse and click**

It uses **pyautogui** to automatically perform:

* `moveTo()` — move the mouse to a specific screen coordinate
* `click()` — click the mouse
* `sleep()` — pause for a moment

In other words, it repeatedly clicks different positions across the entire screen.

---

### **3. Provides three clicking strategies**

* **Sequential clicking:** click through all grid points one by one in order
* **Random clicking:** click a limited number of points in a random order
* **Spiral clicking:** start from the center of the screen and click while drawing a spiral outward
