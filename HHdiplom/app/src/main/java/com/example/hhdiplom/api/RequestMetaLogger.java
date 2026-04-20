// RequestMetaLogger.java
package com.example.hhdiplom.api;

import android.util.Log;

import java.io.IOException;

import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class RequestMetaLogger implements Interceptor {
    @Override
    public Response intercept(Chain chain) throws IOException {
        Request r = chain.request();
        RequestBody b = r.body();

        long len = -1;
        try { if (b != null) len = b.contentLength(); } catch (Exception ignored) {}

        Log.d("HTTP_META", r.method() + " " + r.url());
        Log.d("HTTP_META", "Content-Type=" + (b != null ? b.contentType() : "null") + " len=" + len);
        Log.d("HTTP_META", "Headers:\n" + r.headers());

        return chain.proceed(r);
    }
}
