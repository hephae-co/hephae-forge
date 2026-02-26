fetch("http://localhost:3000/api/discover", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        identity: {
            name: "Bosphorus Nutley",
            address: "Franklin ave nutley nj",
            officialUrl: "https://thebosphorus.us"
        }
    })
}).then(res => res.text()).then(console.log).catch(console.error);
