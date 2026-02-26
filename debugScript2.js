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
    }).then(res => res.text()).then(t => {
        const match = t.match(/Error: Invalid config for agent ([a-zA-Z]+):/);
        if (match) console.log("FOUND SCHEMA ERROR ON AGENT: ", match[1]);
        else console.log("NO MATCH", t.substring(0, 500));
    });
