package com.example.hhdiplom.api;

import android.util.Log;

import okhttp3.Call;
import okhttp3.EventListener;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Proxy;

public class NetEventLogger extends EventListener {
    private static final String T = "NET_EVT";

    @Override public void callStart(Call call) {
        Log.d(T, "callStart " + call.request().method() + " " + call.request().url());
    }

    @Override public void connectStart(Call call, InetSocketAddress addr, Proxy proxy) {
        Log.d(T, "connectStart " + addr);
    }

    @Override public void requestHeadersStart(Call call) { Log.d(T, "requestHeadersStart"); }
    @Override public void requestBodyStart(Call call) { Log.d(T, "requestBodyStart"); }
    @Override public void requestBodyEnd(Call call, long byteCount) { Log.d(T, "requestBodyEnd bytes=" + byteCount); }

    @Override public void responseHeadersStart(Call call) { Log.d(T, "responseHeadersStart"); }
    @Override public void responseHeadersEnd(Call call, okhttp3.Response response) {
        Log.d(T, "responseHeadersEnd code=" + response.code());
    }

    @Override public void callFailed(Call call, IOException ioe) {
        Log.e(T, "callFailed " + ioe, ioe);
    }

    @Override public void callEnd(Call call) {
        Log.d(T, "callEnd");
    }
}
