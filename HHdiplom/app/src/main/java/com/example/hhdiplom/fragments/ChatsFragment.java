package com.example.hhdiplom.fragments;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.example.hhdiplom.R;
import com.example.hhdiplom.activities.ChatMessagesActivity;
import com.example.hhdiplom.adapters.ChatsAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.Chat;
import com.example.hhdiplom.models.ChatResponse;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ChatsFragment extends Fragment {

    private RecyclerView chatsRecyclerView;
    private ProgressBar progressBar;
    private View emptyState;
    private SwipeRefreshLayout swipeRefreshLayout;
    private TextView emptyStateTitle;
    private TextView emptyStateSubtitle;

    private ChatsAdapter chatsAdapter;
    private ApiService apiService;
    private final List<Chat> chatList = new ArrayList<>();

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_chats, container, false);

        initViews(view);
        setupRecyclerView();
        initApiService();
        setupSwipeRefresh();
        loadChats();

        return view;
    }

    private void initViews(View view) {
        chatsRecyclerView = view.findViewById(R.id.chatsRecyclerView);
        progressBar = view.findViewById(R.id.progressBar);
        emptyState = view.findViewById(R.id.emptyState);
        swipeRefreshLayout = view.findViewById(R.id.swipeRefreshLayout);
        emptyStateTitle = view.findViewById(R.id.emptyStateTitle);
        emptyStateSubtitle = view.findViewById(R.id.emptyStateSubtitle);
    }

    private void setupRecyclerView() {
        chatsAdapter = new ChatsAdapter(chatList, chat -> {
            if (getActivity() != null) {
                ChatMessagesActivity.start(
                        getActivity(),
                        chat.getId(),
                        chat.getVacancyId(),
                        chat.getCompanyName(),
                        chat.getVacancyTitle()
                );
            }
        });

        chatsRecyclerView.setLayoutManager(new LinearLayoutManager(getContext()));
        chatsRecyclerView.setAdapter(chatsAdapter);
    }

    private void initApiService() {
        apiService = ApiClient.getApiService();
    }

    private void setupSwipeRefresh() {
        swipeRefreshLayout.setOnRefreshListener(this::loadChats);
        swipeRefreshLayout.setColorSchemeResources(R.color.primary, R.color.accent);
    }

    private void loadChats() {
        if (getActivity() == null) {
            return;
        }

        if (!swipeRefreshLayout.isRefreshing()) {
            progressBar.setVisibility(View.VISIBLE);
        }
        emptyState.setVisibility(View.GONE);

        Call<ChatResponse> call = apiService.getChats();
        call.enqueue(new Callback<ChatResponse>() {
            @Override
            public void onResponse(Call<ChatResponse> call, Response<ChatResponse> response) {
                if (getActivity() == null) {
                    return;
                }

                swipeRefreshLayout.setRefreshing(false);
                progressBar.setVisibility(View.GONE);

                if (response.isSuccessful() && response.body() != null && response.body().getResults() != null) {
                    chatList.clear();
                    chatList.addAll(response.body().getResults());
                    chatsAdapter.notifyDataSetChanged();

                    if (chatList.isEmpty()) {
                        showEmptyState(
                                getString(R.string.chats_empty_title),
                                getString(R.string.chats_empty_subtitle)
                        );
                    }
                } else {
                    showError(getString(R.string.error_with_code, response.code()));
                }
            }

            @Override
            public void onFailure(Call<ChatResponse> call, Throwable t) {
                if (getActivity() == null) {
                    return;
                }

                swipeRefreshLayout.setRefreshing(false);
                progressBar.setVisibility(View.GONE);

                if (chatList.isEmpty()) {
                    showEmptyState(
                            getString(R.string.chats_error_title),
                            getString(R.string.error_network_with_message, t.getMessage())
                    );
                } else {
                    Toast.makeText(getActivity(), getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    private void showEmptyState(String title, String subtitle) {
        emptyState.setVisibility(View.VISIBLE);
        emptyStateTitle.setText(title);
        emptyStateSubtitle.setText(subtitle);
    }

    private void showError(String message) {
        if (getActivity() == null) {
            return;
        }
        if (chatList.isEmpty()) {
            showEmptyState(getString(R.string.chats_error_title), message);
        } else {
            Toast.makeText(getActivity(), message, Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onResume() {
        super.onResume();
        if (getActivity() != null) {
            loadChats();
        }
    }
}
