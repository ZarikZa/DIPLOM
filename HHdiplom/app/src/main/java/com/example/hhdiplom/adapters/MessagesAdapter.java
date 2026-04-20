package com.example.hhdiplom.adapters;

import android.content.Context;
import android.content.res.TypedArray;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.AttrRes;
import androidx.annotation.NonNull;
import androidx.constraintlayout.widget.ConstraintLayout;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.models.Message;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

public class MessagesAdapter extends RecyclerView.Adapter<MessagesAdapter.MessageViewHolder> {

    private final List<Message> messageList;
    private final SimpleDateFormat timeFormat = new SimpleDateFormat("HH:mm", Locale.getDefault());

    public MessagesAdapter(List<Message> messageList) {
        this.messageList = messageList;
    }

    @NonNull
    @Override
    public MessageViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_message, parent, false);
        return new MessageViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull MessageViewHolder holder, int position) {
        Message message = messageList.get(position);
        holder.bind(message);
    }

    @Override
    public int getItemCount() {
        return messageList.size();
    }

    public void addMessage(Message message) {
        messageList.add(message);
        notifyItemInserted(messageList.size() - 1);
    }

    public void updateMessages(List<Message> newMessages) {
        messageList.clear();
        messageList.addAll(newMessages);
        notifyDataSetChanged();
    }

    class MessageViewHolder extends RecyclerView.ViewHolder {
        ConstraintLayout messageContainer;
        TextView messageTextView;
        TextView timeTextView;
        TextView senderNameTextView;

        MessageViewHolder(@NonNull View itemView) {
            super(itemView);
            messageContainer = itemView.findViewById(R.id.messageContainer);
            messageTextView = itemView.findViewById(R.id.messageTextView);
            timeTextView = itemView.findViewById(R.id.timeTextView);
            senderNameTextView = itemView.findViewById(R.id.senderNameTextView);
        }

        void bind(Message message) {
            messageTextView.setText(message.getText());
            timeTextView.setText(formatTime(message.getCreatedAt()));
            messageTextView.setTextAlignment(View.TEXT_ALIGNMENT_VIEW_START);
            messageTextView.setGravity(Gravity.START);
            timeTextView.setTextAlignment(View.TEXT_ALIGNMENT_VIEW_END);

            ConstraintLayout.LayoutParams params = (ConstraintLayout.LayoutParams) messageContainer.getLayoutParams();
            params.startToStart = ConstraintLayout.LayoutParams.PARENT_ID;
            params.endToEnd = ConstraintLayout.LayoutParams.PARENT_ID;
            if (message.isMyMessage()) {
                messageContainer.setBackgroundResource(R.drawable.bg_my_message);
                params.horizontalBias = 1.0f;

                messageTextView.setTextColor(0xFFFFFFFF);
                timeTextView.setTextColor(0xCCFFFFFF);
                senderNameTextView.setVisibility(View.GONE);
            } else {
                messageContainer.setBackgroundResource(R.drawable.bg_other_message);
                params.horizontalBias = 0.0f;

                int textPrimary = resolveAttrColor(itemView.getContext(), R.attr.colorTextPrimary);
                int textSecondary = resolveAttrColor(itemView.getContext(), R.attr.colorTextSecondary);
                messageTextView.setTextColor(textPrimary);
                timeTextView.setTextColor(textSecondary);

                if (message.getSenderName() != null && !message.getSenderName().isEmpty()) {
                    senderNameTextView.setVisibility(View.VISIBLE);
                    senderNameTextView.setText(message.getSenderName());
                    senderNameTextView.setTextColor(textSecondary);
                } else {
                    senderNameTextView.setVisibility(View.GONE);
                }
            }
            messageContainer.setLayoutParams(params);
        }

        private String formatTime(String dateString) {
            if (dateString == null || dateString.isEmpty()) {
                return "";
            }

            try {
                SimpleDateFormat input = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'", Locale.getDefault());
                input.setTimeZone(TimeZone.getTimeZone("UTC"));
                Date date = input.parse(dateString);
                return timeFormat.format(date);
            } catch (Exception ignored) {
            }

            try {
                SimpleDateFormat input = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSSSSX", Locale.getDefault());
                Date date = input.parse(dateString);
                return timeFormat.format(date);
            } catch (Exception ignored) {
            }

            try {
                SimpleDateFormat input = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.getDefault());
                input.setTimeZone(TimeZone.getTimeZone("UTC"));
                Date date = input.parse(dateString);
                return timeFormat.format(date);
            } catch (Exception ignored) {
            }

            return "";
        }
    }

    private int resolveAttrColor(Context context, @AttrRes int attrId) {
        TypedArray ta = context.obtainStyledAttributes(new int[]{attrId});
        int color = ta.getColor(0, 0xFF000000);
        ta.recycle();
        return color;
    }
}
