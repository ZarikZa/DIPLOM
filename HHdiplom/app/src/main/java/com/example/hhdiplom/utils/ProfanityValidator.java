package com.example.hhdiplom.utils;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class ProfanityValidator {

    private static final Pattern TOKEN_RE = Pattern.compile("[A-Za-z\\u0400-\\u04FF0-9]+");

    private static final List<String> BLOCKED_STEMS = Arrays.asList(
            "\u0431\u043b\u044f",
            "\u0431\u043b\u044f\u0434",
            "\u043f\u0438\u0437\u0434",
            "\u0445\u0443\u0439",
            "\u0445\u0443\u0435",
            "\u0435\u0431\u0430",
            "\u0435\u0431\u043b",
            "\u0435\u0431\u043d",
            "\u0435\u0431\u0443\u0447",
            "\u043f\u0438\u0434\u043e\u0440",
            "\u043f\u0438\u0434\u0430\u0440",
            "\u0434\u043e\u043b\u0431\u043e\u0435\u0431",
            "\u0434\u043e\u043b\u0431\u0430\u0435\u0431",
            "\u043c\u0443\u0434\u0438\u043b",
            "\u0433\u0430\u043d\u0434\u043e\u043d",
            "\u0437\u0430\u043b\u0443\u043f",
            "suka",
            "blya",
            "xuy",
            "huy",
            "pizd",
            "eban",
            "fuck",
            "shit",
            "bitch",
            "cunt",
            "asshole",
            "motherf"
    );

    public static final String DEFAULT_ERROR_MESSAGE =
            "\u0422\u0435\u043a\u0441\u0442 \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u0442 \u043d\u0435\u0446\u0435\u043d\u0437\u0443\u0440\u043d\u0443\u044e \u043b\u0435\u043a\u0441\u0438\u043a\u0443";

    private ProfanityValidator() {
    }

    public static boolean containsProfanity(String value) {
        if (value == null || value.trim().isEmpty()) {
            return false;
        }

        Matcher matcher = TOKEN_RE.matcher(value);
        while (matcher.find()) {
            String token = normalizeToken(matcher.group());
            for (String stem : BLOCKED_STEMS) {
                if (token.contains(stem)) {
                    return true;
                }
            }
        }

        return false;
    }

    private static String normalizeToken(String rawToken) {
        if (rawToken == null) {
            return "";
        }

        String token = rawToken.toLowerCase(Locale.ROOT)
                .replace('\u0451', '\u0435');

        StringBuilder mapped = new StringBuilder(token.length());
        for (int i = 0; i < token.length(); i++) {
            mapped.append(mapLeet(token.charAt(i)));
        }

        return collapseLongRepeats(mapped.toString());
    }

    private static char mapLeet(char ch) {
        switch (ch) {
            case '@':
            case '4':
                return 'a';
            case '$':
            case '5':
                return 's';
            case '0':
                return 'o';
            case '1':
                return 'i';
            case '3':
                return 'e';
            case '6':
            case '8':
                return 'b';
            case '7':
                return 't';
            case '9':
                return 'g';
            default:
                return ch;
        }
    }

    private static String collapseLongRepeats(String text) {
        if (text.length() < 3) {
            return text;
        }

        StringBuilder result = new StringBuilder(text.length());
        char prev = 0;
        int repeats = 0;

        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch == prev) {
                repeats++;
            } else {
                repeats = 1;
                prev = ch;
            }

            if (repeats <= 2) {
                result.append(ch);
            }
        }

        return result.toString();
    }
}
