// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getFirestore, collection, addDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-analytics.js";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyAD5z1Lz97oveMiQYB13e7C7jTD_rYruLs",
    authDomain: "concalab-uasd-64ff4.firebaseapp.com",
    projectId: "concalab-uasd-64ff4",
    storageBucket: "concalab-uasd-64ff4.firebasestorage.app",
    messagingSenderId: "541228093310",
    appId: "1:541228093310:web:d75d199a26086c9965ed2f",
    measurementId: "G-4T02MVWP7F"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
const db = getFirestore(app);

export { db, collection, addDoc, serverTimestamp };
