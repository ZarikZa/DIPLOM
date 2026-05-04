package com.example.hhdiplom.activities;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.adapters.MessagesAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.Message;
import com.example.hhdiplom.models.SendMessageRequest;
import com.example.hhdiplom.utils.ProfanityValidator;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ChatMessagesActivity extends AppCompatActivity {

    private static final String EXTRA_CHAT_ID = "CHAT_ID";
    private static final String EXTRA_VACANCY_ID = "VACANCY_ID";
    private static final String EXTRA_COMPANY_NAME = "COMPANY_NAME";
    private static final String EXTRA_VACANCY_TITLE = "VACANCY_TITLE";
    private static final long POLL_INTERVAL_MS = 3000L;

    private RecyclerView messagesRecyclerView;
    private EditText messageEditText;
    private ImageButton sendButton;
    private ImageButton backButton;
    private ProgressBar progressBar;
    private TextView toolbarTitle;
    private TextView toolbarSubtitle;
    private View headerContainer;
    private View headerArrow;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable pollingRunnable;

    private MessagesAdapter messagesAdapter;
    private ApiService apiService;
    private final List<Message> messageList = new ArrayList<>();

    private int chatId;
    private int vacancyId;
    private String companyName;
    private String vacancyTitle;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_chat_messages);

        if (!readIntentExtras()) {
            finish();
            return;
        }

        initViews();
        setupToolbar();
        setupRecyclerView();
        initApiService();
        setupMessageInput();
        loadMessages();
    }

    private boolean readIntentExtras() {
        Intent intent = getIntent();
        if (intent == null) {
            return false;
        }

        chatId = intent.getIntExtra(EXTRA_CHAT_ID, -1);
        if (chatId <= 0) {
            return false;
        }

        vacancyId = intent.getIntExtra(EXTRA_VACANCY_ID, -1);
        companyName = intent.getStringExtra(EXTRA_COMPANY_NAME);
        vacancyTitle = intent.getStringExtra(EXTRA_VACANCY_TITLE);
        return true;
    }

    private void initViews() {
        messagesRecyclerView = findViewById(R.id.messagesRecyclerView);
        messageEditText = findViewById(R.id.messageEditText);
        sendButton = findViewById(R.id.sendButton);
        backButton = findViewById(R.id.backButton);
        progressBar = findViewById(R.id.progressBar);
        toolbarTitle = findViewById(R.id.toolbarTitle);
        toolbarSubtitle = findViewById(R.id.toolbarSubtitle);
        headerContainer = findViewById(R.id.headerContainer);
        headerArrow = findViewById(R.id.headerArrow);

        backButton.setOnClickListener(v -> finish());
        sendButton.setEnabled(false);
    }

    private void setupToolbar() {
        toolbarTitle.setText(safeText(companyName, R.string.chat_title_fallback));
        toolbarSubtitle.setText(safeText(vacancyTitle, R.string.chat_vacancy_fallback));

        boolean canOpenVacancy = vacancyId > 0;
        headerContainer.setEnabled(canOpenVacancy);
        headerContainer.setOnClickListener(canOpenVacancy ? v -> openVacancy() : null);
        headerContainer.setAlpha(canOpenVacancy ? 1f : 0.6f);
        headerArrow.setVisibility(canOpenVacancy ? View.VISIBLE : View.GONE);
    }

    private void setupRecyclerView() {
        messagesAdapter = new MessagesAdapter(messageList);
        LinearLayoutManager layoutManager = new LinearLayoutManager(this);
        layoutManager.setStackFromEnd(true);

        messagesRecyclerView.setLayoutManager(layoutManager);
        messagesRecyclerView.setAdapter(messagesAdapter);
    }

    private void initApiService() {
        apiService = ApiClient.getApiService();
    }

    private void setupMessageInput() {
        messageEditText.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                sendButton.setEnabled(s != null && s.toString().trim().length() > 0);
            }

            @Override
            public void afterTextChanged(Editable s) {
            }
        });

        sendButton.setOnClickListener(v -> sendMessage());
        messageEditText.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == android.view.inputmethod.EditorInfo.IME_ACTION_SEND) {
                sendMessage();
                return true;
            }
            return false;
        });
    }

    private void loadMessages() {
        progressBar.setVisibility(View.VISIBLE);

        apiService.getChatMessages(chatId).enqueue(new Callback<List<Message>>() {
            @Override
            public void onResponse(@NonNull Call<List<Message>> call, @NonNull Response<List<Message>> response) {
                progressBar.setVisibility(View.GONE);

                if (!response.isSuccessful() || response.body() == null) {
                    Toast.makeText(ChatMessagesActivity.this,
                            getString(R.string.error_with_code, response.code()),
                            Toast.LENGTH_SHORT).show();
                    return;
                }

                updateMessages(response.body(), true);
                startPolling();
            }

            @Override
            public void onFailure(@NonNull Call<List<Message>> call, @NonNull Throwable t) {
                progressBar.setVisibility(View.GONE);
                Toast.makeText(ChatMessagesActivity.this,
                        getString(R.string.error_network_with_message, t.getMessage()),
                        Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void sendMessage() {
        final String text = messageEditText.getText().toString().trim();
        if (text.isEmpty()) {
            return;
        }
        if (ProfanityValidator.containsProfanity(text)) {
            Toast.makeText(this, ProfanityValidator.DEFAULT_ERROR_MESSAGE, Toast.LENGTH_SHORT).show();
            return;
        }

        sendButton.setEnabled(false);
        messageEditText.setText("");

        apiService.sendMessage(chatId, new SendMessageRequest(text)).enqueue(new Callback<Message>() {
            @Override
            public void onResponse(@NonNull Call<Message> call, @NonNull Response<Message> response) {
                sendButton.setEnabled(messageEditText.getText().toString().trim().length() > 0);

                if (response.isSuccessful() && response.body() != null) {
                    messageList.add(response.body());
                    messagesAdapter.notifyItemInserted(messageList.size() - 1);
                    scrollToBottom();
                    return;
                }

                messageEditText.setText(text);
                messageEditText.setSelection(messageEditText.getText().length());
                Toast.makeText(ChatMessagesActivity.this,
                        getString(R.string.error_with_code, response.code()),
                        Toast.LENGTH_SHORT).show();
            }

            @Override
            public void onFailure(@NonNull Call<Message> call, @NonNull Throwable t) {
                sendButton.setEnabled(messageEditText.getText().toString().trim().length() > 0);
                messageEditText.setText(text);
                messageEditText.setSelection(messageEditText.getText().length());
                Toast.makeText(ChatMessagesActivity.this,
                        getString(R.string.error_network_with_message, t.getMessage()),
                        Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void startPolling() {
        stopPolling();
        pollingRunnable = new Runnable() {
            @Override
            public void run() {
                checkNewMessages();
                handler.postDelayed(this, POLL_INTERVAL_MS);
            }
        };
        handler.postDelayed(pollingRunnable, POLL_INTERVAL_MS);
    }

    private void stopPolling() {
        if (pollingRunnable != null) {
            handler.removeCallbacks(pollingRunnable);
            pollingRunnable = null;
        }
    }

    private void checkNewMessages() {
        apiService.getChatMessages(chatId).enqueue(new Callback<List<Message>>() {
            @Override
            public void onResponse(@NonNull Call<List<Message>> call, @NonNull Response<List<Message>> response) {
                if (!response.isSuccessful() || response.body() == null) {
                    return;
                }
                updateMessages(response.body(), false);
            }

            @Override
            public void onFailure(@NonNull Call<List<Message>> call, @NonNull Throwable t) {
            }
        });
    }

    private void updateMessages(@NonNull List<Message> newMessages, boolean forceScroll) {
        boolean hasChanges = messageList.size() != newMessages.size();
        if (!hasChanges) {
            for (int i = 0; i < newMessages.size(); i++) {
                if (messageList.get(i).getId() != newMessages.get(i).getId()) {
                    hasChanges = true;
                    break;
                }
            }
        }

        if (!hasChanges) {
            return;
        }

        boolean hasNewTail = newMessages.size() > messageList.size();
        messageList.clear();
        messageList.addAll(newMessages);
        messagesAdapter.notifyDataSetChanged();

        if (forceScroll || hasNewTail) {
            scrollToBottom();
        }
    }

    private void scrollToBottom() {
        if (messagesAdapter.getItemCount() > 0) {
            messagesRecyclerView.scrollToPosition(messagesAdapter.getItemCount() - 1);
        }
    }

    private void openVacancy() {
        if (vacancyId <= 0) {
            return;
        }
        Intent intent = new Intent(this, VacancyDetailsActivity.class);
        intent.putExtra("vacancy_id", vacancyId);
        startActivity(intent);
    }

    private String safeText(String value, int fallbackResId) {
        if (value == null) {
            return getString(fallbackResId);
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? getString(fallbackResId) : trimmed;
    }

    @Override
    protected void onResume() {
        super.onResume();
        startPolling();
    }

    @Override
    protected void onPause() {
        stopPolling();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        stopPolling();
        super.onDestroy();
    }

    public static void start(@NonNull Activity activity,
                             int chatId,
                             int vacancyId,
                             String companyName,
                             String vacancyTitle) {
        activity.startActivity(createIntent(activity, chatId, vacancyId, companyName, vacancyTitle));
    }

    public static void start(@NonNull Activity activity, int chatId) {
        start(activity, chatId, -1, null, null);
    }

    @NonNull
    public static Intent createIntent(@NonNull Context context,
                                      int chatId,
                                      int vacancyId,
                                      String companyName,
                                      String vacancyTitle) {
        Intent intent = new Intent(context, ChatMessagesActivity.class);
        intent.putExtra(EXTRA_CHAT_ID, chatId);
        intent.putExtra(EXTRA_VACANCY_ID, vacancyId);
        intent.putExtra(EXTRA_COMPANY_NAME, companyName);
        intent.putExtra(EXTRA_VACANCY_TITLE, vacancyTitle);
        return intent;
    }
}
