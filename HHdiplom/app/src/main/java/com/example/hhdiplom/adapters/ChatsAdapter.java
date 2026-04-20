package com.example.hhdiplom.adapters;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.cardview.widget.CardView;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.models.Chat;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

public class ChatsAdapter extends RecyclerView.Adapter<ChatsAdapter.ChatViewHolder> {

    private List<Chat> chatList;
    private final OnChatClickListener listener;

    public interface OnChatClickListener {
        void onChatClick(Chat chat);
    }

    public ChatsAdapter(List<Chat> chatList, OnChatClickListener listener) {
        this.chatList = chatList;
        this.listener = listener;
    }

    @NonNull
    @Override
    public ChatViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_chat, parent, false);
        return new ChatViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ChatViewHolder holder, int position) {
        if (position >= chatList.size()) {
            return;
        }

        Chat chat = chatList.get(position);
        if (chat == null) {
            return;
        }

        holder.bind(chat);
        holder.itemView.setOnClickListener(v -> {
            if (listener != null) {
                listener.onChatClick(chat);
            }
        });
    }

    @Override
    public int getItemCount() {
        return chatList != null ? chatList.size() : 0;
    }

    public void updateChats(List<Chat> newChats) {
        if (chatList == null) {
            chatList = new java.util.ArrayList<>();
        }
        chatList.clear();
        if (newChats != null) {
            chatList.addAll(newChats);
        }
        notifyDataSetChanged();
    }

    static class ChatViewHolder extends RecyclerView.ViewHolder {
        CardView cardView;
        TextView companyNameTextView;
        TextView vacancyPositionTextView;
        TextView lastMessageTextView;
        TextView timeTextView;
        TextView unreadBadgeTextView;

        ChatViewHolder(@NonNull View itemView) {
            super(itemView);
            cardView = itemView.findViewById(R.id.cardView);
            companyNameTextView = itemView.findViewById(R.id.companyNameTextView);
            vacancyPositionTextView = itemView.findViewById(R.id.vacancyPositionTextView);
            lastMessageTextView = itemView.findViewById(R.id.lastMessageTextView);
            timeTextView = itemView.findViewById(R.id.timeTextView);
            unreadBadgeTextView = itemView.findViewById(R.id.unreadBadgeTextView);
        }

        void bind(Chat chat) {
            companyNameTextView.setText(nonEmpty(chat.getCompanyName(), R.string.chat_title_fallback));
            vacancyPositionTextView.setText(nonEmpty(chat.getVacancyTitle(), R.string.chat_vacancy_fallback));

            Chat.LastMessage lastMessage = chat.getLastMessage();
            if (lastMessage != null && lastMessage.getText() != null && !lastMessage.getText().isEmpty()) {
                String message = lastMessage.getText();
                if (message.length() > 70) {
                    message = message.substring(0, 67) + "...";
                }
                lastMessageTextView.setText(message);

                String createdAt = lastMessage.getCreatedAt();
                timeTextView.setText(formatTime(createdAt));
            } else {
                lastMessageTextView.setText(itemView.getContext().getString(R.string.chats_no_messages));
                timeTextView.setText("");
            }

            if (chat.getUnreadCount() > 0) {
                unreadBadgeTextView.setVisibility(View.VISIBLE);
                unreadBadgeTextView.setText(String.valueOf(chat.getUnreadCount()));
            } else {
                unreadBadgeTextView.setVisibility(View.GONE);
            }
        }

        private String nonEmpty(String value, int fallbackResId) {
            if (value == null) {
                return itemView.getContext().getString(fallbackResId);
            }
            String trimmed = value.trim();
            return trimmed.isEmpty() ? itemView.getContext().getString(fallbackResId) : trimmed;
        }

        private String formatTime(String dateString) {
            if (dateString == null || dateString.isEmpty()) {
                return "";
            }

            try {
                SimpleDateFormat input = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'", Locale.getDefault());
                input.setTimeZone(TimeZone.getTimeZone("UTC"));
                Date d = input.parse(dateString);
                return new SimpleDateFormat("HH:mm", Locale.getDefault()).format(d);
            } catch (Exception ignored) {
            }

            try {
                SimpleDateFormat input = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSSSSX", Locale.getDefault());
                Date d = input.parse(dateString);
                return new SimpleDateFormat("HH:mm", Locale.getDefault()).format(d);
            } catch (Exception ignored) {
            }

            try {
                SimpleDateFormat input = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.getDefault());
                input.setTimeZone(TimeZone.getTimeZone("UTC"));
                Date d = input.parse(dateString);
                return new SimpleDateFormat("HH:mm", Locale.getDefault()).format(d);
            } catch (Exception ignored) {
            }

            return "";
        }
    }
}
