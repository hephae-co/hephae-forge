fetch("http://localhost:3000/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            enrichedProfile: {
                name: "Test Diner",
                address: "New Jersey",
                officialUrl: "https://example.com",
                menuScreenshotBase64: "data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
                persona: "Classic NJ Diner"
            }
        })
    }).then(res => res.text()).then(t => console.log(t.substring(0,2500)));
