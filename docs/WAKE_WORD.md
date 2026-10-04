# Wake word badalna ("Hey Roohvi")

## Ab kya hota hai
- Wake word **optional** hai aur default me band hai. Mic ke saath hamesha WAKE NOW button bhi hai.
- openWakeWord ke stock phrases sirf yeh hain: alexa, hey_mycroft, hey_jarvis, hey_marvin, timer, weather.
  **"Hey Roohvi" in me nahi hai**, is liye uske liye apna model train karna padta hai.
- Jab tak custom model nahi hota, app stock **"Hey Mycroft"** istemal karti hai (aur screen/log me wahi phrase dikhati hai).

## Apna "Hey Roohvi" model (lagbhag 1 ghanta, free Colab)
1. openWakeWord ka GitHub repo kholo (dscripka/openWakeWord) aur uska **automatic training notebook** (Colab) chalao.
   Notebook ke kaam ke naam/steps badal sakte hain, is liye uska README saath me dekhna.
2. Target phrase me `hey roohvi` likho. Agar bolne me "mind care" jaisa nikalta ho to dono tarah ke likhne
   (jaise `hey mind care`) bhi try karo.
3. Training ke baad `hey_roohvi.onnx` (aur chahein to `.tflite`) download karo.
4. File ko **`models/wake/`** folder me rakh do. Baaki kuch nahi karna: app khud pehchan leti hai.
5. App ke wake word button se (agar pehli baar ho) "download" dabao. Yeh sirf shared feature models laata hai.

## Dhyan rakhne ki baatein
- **Accent:** Notebook mostly English synthetic awaaz se train karta hai. Pakistani lehje me kam pakad sakta hai.
  Apne team ke 5 logon se 20-30 baar bulwa kar test karo. Kam pakde to `DEFAULT_THRESHOLD` (core/wake_word.py, 0.5) thoda
  kam karo; zyada ghalat jaag jaye to barhao.
- **Ghalat jaagna aur na jaagna dono ka asar hai.** Pareshan insaan ke liye na jaagna zyada bura hai, is liye
  **WAKE NOW button hamesha rakho.**
- Mic ka audio is feature me bhi sirf device par chalta hai (model local hai).

## Phrase ka text badalna
`config/api_keys.json` me:
```
"wake_phrase": "Hey Roohvi",
"wake_model": "hey_marvin",            // sirf stock model badalna ho to
"wake_model_path": "C:/path/my.onnx"   // ya koi bhi custom file ka seedha path
```
Order: wake_model_path -> models/wake/*.onnx -> wake_model -> hey_mycroft.
