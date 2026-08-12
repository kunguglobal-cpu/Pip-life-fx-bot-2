package com.piplifefx.bot;

import android.app.*;
import android.content.*;
import android.os.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class BotService extends Service {
    Thread worker;
    @Override public void onCreate() {
        super.onCreate();
        String channel="piplife_bot";
        NotificationChannel nc=new NotificationChannel(channel,"Pip-life FX Bot",NotificationManager.IMPORTANCE_LOW);
        ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(nc);
        startForeground(7,new Notification.Builder(this,channel)
            .setContentTitle("Pip-life FX Bot")
            .setContentText("Bot service running")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .build());
    }

    @Override public int onStartCommand(Intent intent,int flags,int id) {
        String token=intent.getStringExtra("token");
        String account=intent.getStringExtra("account");
        boolean live=intent.getBooleanExtra("live",false);
        if(!Python.isStarted()) Python.start(new AndroidPlatform(this));
        if(worker==null || !worker.isAlive()) {
            worker=new Thread(() -> {
                try {
                    Python.getInstance().getModule("launcher").callAttr("run_bot",token,account,live);
                } catch(Exception e) {
                    try { Python.getInstance().getModule("launcher").callAttr("write_log","SERVICE ERROR | "+e); } catch(Exception ignored){}
                }
            });
            worker.start();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        try { if(Python.isStarted()) Python.getInstance().getModule("launcher").callAttr("stop_bot"); } catch(Exception ignored){}
        super.onDestroy();
    }

    @Override public android.os.IBinder onBind(Intent intent) { return null; }
}
