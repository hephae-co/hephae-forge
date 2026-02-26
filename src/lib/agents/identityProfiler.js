"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.analyzeBusinessIdentity = analyzeBusinessIdentity;
var playwright_1 = require("playwright");
var generative_ai_1 = require("@google/generative-ai");
function resolveUrlFromName(name) {
    return __awaiter(this, void 0, void 0, function () {
        var genAI, model, prompt, result, resolvedUrl;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    if (!process.env.GEMINI_API_KEY) {
                        throw new Error("Missing GEMINI_API_KEY for URL resolution");
                    }
                    genAI = new generative_ai_1.GoogleGenerativeAI(process.env.GEMINI_API_KEY);
                    model = genAI.getGenerativeModel({
                        model: "gemini-3-flash-preview",
                        tools: [{
                                // @ts-ignore
                                googleSearch: {}
                            }]
                    }, { baseUrl: "https://generativelanguage.googleapis.com" });
                    prompt = "Find the Official Website URL for the restaurant/business named \"".concat(name, "\".\nReturn ONLY the raw URL as your response. Do not include any markdown, explanations, or quotes.\nIf you cannot find an official website, try to return their facebook page or Yelp page.");
                    return [4 /*yield*/, model.generateContent(prompt)];
                case 1:
                    result = _a.sent();
                    resolvedUrl = result.response.text().trim();
                    if (!resolvedUrl.startsWith('http')) {
                        resolvedUrl = 'https://' + resolvedUrl;
                    }
                    return [2 /*return*/, resolvedUrl];
            }
        });
    });
}
function analyzeBusinessIdentity(url) {
    return __awaiter(this, void 0, void 0, function () {
        var browser, targetUrl, err_1, context, page, name_1, colors, logoUrl, persona, menuScreenshotBase64, menuHref, buffer, err_2, error_1;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    _a.trys.push([0, 24, 25, 28]);
                    targetUrl = url;
                    if (!(!url.startsWith('http') && (!url.includes('.') || url.includes(' ')))) return [3 /*break*/, 5];
                    console.log("Input \"".concat(url, "\" looks like a name. Resolving to URL via Gemini Search..."));
                    _a.label = 1;
                case 1:
                    _a.trys.push([1, 3, , 4]);
                    return [4 /*yield*/, resolveUrlFromName(url)];
                case 2:
                    targetUrl = _a.sent();
                    console.log("Resolved name to URL: ".concat(targetUrl));
                    return [3 /*break*/, 4];
                case 3:
                    err_1 = _a.sent();
                    console.error("Failed to resolve URL from name:", err_1);
                    throw new Error("Could not find a valid website for the provided business name.");
                case 4: return [3 /*break*/, 6];
                case 5:
                    if (!url.startsWith('http')) {
                        targetUrl = 'https://' + url;
                    }
                    _a.label = 6;
                case 6: return [4 /*yield*/, playwright_1.chromium.launch()];
                case 7:
                    browser = _a.sent();
                    return [4 /*yield*/, browser.newContext({ ignoreHTTPSErrors: true })];
                case 8:
                    context = _a.sent();
                    return [4 /*yield*/, context.newPage()];
                case 9:
                    page = _a.sent();
                    return [4 /*yield*/, page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 15000 })];
                case 10:
                    _a.sent();
                    return [4 /*yield*/, page.title().then(function (t) { return t.split('|')[0].split('-')[0].trim(); })];
                case 11:
                    name_1 = (_a.sent()) || "Unknown Business";
                    return [4 /*yield*/, page.evaluate(function () {
                            var getBg = function (el) { return window.getComputedStyle(el).backgroundColor; };
                            var bodyBg = getBg(document.body);
                            var header = document.querySelector('header, nav, .navbar');
                            var headerBg = header ? getBg(header) : 'rgb(0,0,0)';
                            var rgbToHex = function (rgb) {
                                var result = rgb.match(/\d+/g);
                                if (!result || result.length < 3)
                                    return "#000000";
                                return "#" + ((1 << 24) + (parseInt(result[0]) << 16) + (parseInt(result[1]) << 8) + (parseInt(result[2]))).toString(16).slice(1);
                            };
                            return {
                                primary: rgbToHex(headerBg !== 'rgba(0, 0, 0, 0)' ? headerBg : bodyBg),
                                secondary: rgbToHex(bodyBg)
                            };
                        })];
                case 12:
                    colors = _a.sent();
                    return [4 /*yield*/, page.evaluate(function () {
                            var img = document.querySelector('img[src*="logo"], header img');
                            return img ? img.src : undefined;
                        })];
                case 13:
                    logoUrl = _a.sent();
                    return [4 /*yield*/, page.evaluate(function () {
                            var text = document.body.innerText.toLowerCase();
                            if (text.includes("est.") || text.includes("family owned") || text.includes("since 19"))
                                return "Old School Jersey Diner";
                            if (text.includes("artisanal") || text.includes("organic") || text.includes("brew"))
                                return "Modern Cafe";
                            return "Classic Neighborhood Spot";
                        })];
                case 14:
                    persona = _a.sent();
                    menuScreenshotBase64 = void 0;
                    _a.label = 15;
                case 15:
                    _a.trys.push([15, 22, , 23]);
                    console.log("Looking for menu link...");
                    return [4 /*yield*/, page.evaluate(function () {
                            var anchors = Array.from(document.querySelectorAll('a'));
                            // Look for links with "menu" in text or href
                            var menuLink = anchors.find(function (a) {
                                return (a.innerText && a.innerText.toLowerCase().includes('menu')) ||
                                    (a.href && a.href.toLowerCase().includes('menu'));
                            });
                            return menuLink ? menuLink.href : null;
                        })];
                case 16:
                    menuHref = _a.sent();
                    if (!menuHref) return [3 /*break*/, 18];
                    console.log("Found menu link:", menuHref);
                    // Navigate to menu page
                    return [4 /*yield*/, page.goto(menuHref, { waitUntil: 'domcontentloaded', timeout: 10000 })];
                case 17:
                    // Navigate to menu page
                    _a.sent();
                    return [3 /*break*/, 19];
                case 18:
                    console.log("No menu link found, assuming homepage is the menu.");
                    _a.label = 19;
                case 19: 
                // Wait for potential lazy loads
                return [4 /*yield*/, page.waitForTimeout(2000)];
                case 20:
                    // Wait for potential lazy loads
                    _a.sent();
                    return [4 /*yield*/, page.screenshot({ fullPage: true, type: 'jpeg', quality: 60 })];
                case 21:
                    buffer = _a.sent();
                    menuScreenshotBase64 = buffer.toString('base64');
                    console.log("Menu screenshot captured.");
                    return [3 /*break*/, 23];
                case 22:
                    err_2 = _a.sent();
                    console.warn("Menu discovery failed:", err_2);
                    return [3 /*break*/, 23];
                case 23: return [2 /*return*/, {
                        name: name_1,
                        primaryColor: colors.primary,
                        secondaryColor: colors.secondary,
                        logoUrl: logoUrl,
                        persona: persona,
                        menuScreenshotBase64: menuScreenshotBase64 // Return the crawled menu
                    }];
                case 24:
                    error_1 = _a.sent();
                    console.error("Identity Profiler Failed:", error_1);
                    return [2 /*return*/, {
                            name: "Your Business",
                            primaryColor: "#1e3a8a",
                            secondaryColor: "#ffffff",
                            persona: "Classic Neighborhood Spot"
                        }];
                case 25:
                    if (!browser) return [3 /*break*/, 27];
                    return [4 /*yield*/, browser.close()];
                case 26:
                    _a.sent();
                    _a.label = 27;
                case 27: return [7 /*endfinally*/];
                case 28: return [2 /*return*/];
            }
        });
    });
}
