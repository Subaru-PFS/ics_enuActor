    
    
    
    
    #include <SPI.h>
    #include <Ethernet2.h>
    
    #include <MsTimer2.h>
    
    
    
    // Enter a MAC address and IP address for your controller below.
    // The IP address will be dependent on your local network.
    // gateway and subnet are optional:
    
    byte mac[] =
    {
      0x90, 0xA2, 0xDA, 0x0F, 0xA0, 0x4F
    };
    
    
    String Commands[] =
    {
      "bia_on", 
      "bia_off",
      "shut_open", 
      "shut_close",
      "reboot",
      "blue_open", 
      "blue_close",
      "red_open", 
      "red_close",
      "init"
    };
    #define COMMANDS_COUNT  10
    
    
    
    // telnet defaults to port 23
    EthernetServer g_server(23);
    
    
    // BIA Controller MODES
    int bia_mode;
    bool BIAIsOn;
    
    int g_pin; // bia pin#
    long g_aduty; // duty
    long g_aperiod; // period
    
    boolean shb_open_status;
    boolean shb_close_status;
    boolean shb_err_status;
    boolean shr_open_status;
    boolean shr_close_status;
    boolean shr_err_status;
    
    bool LedState;
    bool PulseMode;
    
    #define STATUS_BCRC        0x52 //Both shutters closed no error
    #define STATUS_BCRO        0x54 //Blue CLOSED Red OPEN no error
    #define STATUS_BORC        0x62 //Blue OPEN Red CLOSED no error
    #define STATUS_BORO        0x64 //Blue OPEN Red OPEN no error
    
    int ShutterMotionTimeout = 2000;
    
    /*
     ///// LECTURE EFFECTIVE DES STATUS SUR PORT IO ARDUINO //
      shb_open_status = digitalRead(8);       // BS ouvert//
      shb_close_status = digitalRead(5); // BS ferme //
      shb_err_status = digitalRead(1); // BS error //
      shr_open_status = digitalRead(3); // RS ouvert //
      shr_close_status = digitalRead(4);  // RS fermé //
      shr_err_status = digitalRead(2);  //RS error //
    */
    
    int StatWord;
    
    // setup
    void setup()
    {
      Serial.begin(9600);
      // this check is only needed on the Leonardo:
      Serial.println("BIADuino v2.1");
    
      if (Ethernet.begin(mac) == 0) 
      {
        Serial.println("Failed to configure Ethernet using DHCP");
        // no point in carrying on, so do nothing forevermore:
        for (;;);
      }
    
      g_server.begin();
    
      Serial.println(Ethernet.localIP());
      delay(1000);
    
      LedState = false;
      PulseMode = false;
    
      // Set BIA :ode to IDLE
      bia_mode = 0;
    
      //////////////////////////////////// PARAM BIA /////////////////////////////////////////
      g_aduty = 0; // 0% duty
      g_aperiod = 100; // 100000 = 100ms 1000 = 1ms
      g_pin = 9;
      BIAIsOn = false;
    
    
      //////////////////////////////////// PARAM SHUTTERS /////////////////////////////////////////
      // Config pin 7 en output (DF)
      pinMode(1, INPUT);
      pinMode(2, INPUT);
      pinMode(3, INPUT);
      pinMode(4, INPUT);
      pinMode(5, INPUT);
      pinMode(6, OUTPUT);
      pinMode(7, OUTPUT);
      pinMode(8, INPUT);
    
      pinMode(g_pin, OUTPUT);
      digitalWrite(g_pin, LOW);
      digitalWrite(6, LOW);
      digitalWrite(g_pin, LOW);
    
      MsTimer2::set(1000, Timer); // 500ms period
      MsTimer2::start();
    }
    
    //ISR(TIMER1_COMPA_vect)
    void Timer()
    { //timer1 interrupt 1Hz
      if (BIAIsOn)
      {
        if (!PulseMode)
        {
          analogWrite(g_pin, g_aduty);
          return;
        }
    
        if (LedState)
        {
          
          //Serial.print("ON ");
          //Serial.println(g_aduty);
          analogWrite(g_pin, g_aduty);
          //digitalWrite(9, HIGH);
        }
        else
        {
          //Serial.println("OFF");
          digitalWrite(g_pin, LOW);
        }
        LedState = !LedState;
      }
    }
    
    int CommandCode(String comm)
    {
      int i;
      bool found;
    
      i = 0;
      found = false;
      while ((i < COMMANDS_COUNT) && (!CheckCommand(comm, Commands[i])))
        i++;
    
      return i;
    }
    
    bool StatusEvolve(int command, EthernetClient g_client)
    {
      bool cmdOk = false;
    
      switch (bia_mode)
      {
        case 0: // == everything OFF
          {
            switch (command)
            {
              case 0://bia_on, OK
                bia_mode = 10;
                cmdOk = true;
                break;
    
              case 1://bia_off while already off NOK
                break;
    
              case 2://shut_open : open both shutters OK
                bia_mode = 20;
                cmdOk = true;
                break;
    
              case 3://shut_close while they are already closed NOK
                break;
    
              case 4://reboot OK
                break;
    
              case 5://blue_open : open blue shutter only OK
                bia_mode = 30;
                cmdOk = true;
                break;
    
              case 6://blue_close while blue shutter is already closed NOK
                break;
    
              case 7://red_open : open red shutter only OK
                bia_mode = 40;
                cmdOk = true;
                break;
    
              case 8://red_close : close red shutter while already closed NOK
                break;

              case 9://init : close both shutters, bia_off OK
                bia_mode = 0;
                cmdOk = true;
                break;

              case 10://error / command not found NOK
                break;

            }
            break;
          }
    
        case 10: // == BIA is ON
          {
            switch (command)
            {
              case 0://bia_on
                break;
    
              case 1://bia_off
                bia_mode = 0;
                cmdOk = true;
                break;
    
              case 2://shut_open, INTERLOCK NOK
                break;
    
              case 3://shut_close while shutters are already closed NOK
                break;
    
              case 4://reboot
                break;
    
              case 5://blue_open, INTERLOCK NOK
                break;
    
              case 6://blue_close while shutter blue is already closed NOK
                break;
    
              case 7://red_open, INTERLOCK NOK
                break;
    
              case 8://red_close while shutter red already closed NOK
                break;
    
              case 9://init : close both shutters, bia_off, OK
                bia_mode = 0;
                cmdOk = true;
                break;

              case 10://error / command not found NOK
                break;
            }
            break;
          }
    
        case 20: // == Shutters are OPEN
          {
            switch (command)
            {
              case 0://bia_on, INTERLOCK NOK
                break;
    
              case 1://bia_off while bia is already off NOK
                break;
    
              case 2://shut_open while shutters are already open NOK
                break;
    
              case 3://shut_close : close both shutters OK
                bia_mode = 0;
                cmdOk = true;
                break;
    
              case 4://reboot OK
                break;
    
              case 5://blue_open while shutter blue is already open, NOK
                break;
    
              case 6://blue_close : close blue shutter only OK
                bia_mode = 40;
                cmdOk = true;
                break;
    
              case 7://red_open while shutter red is already open, NOK
                break;
    
              case 8://red_close : close red shutter only OK
                bia_mode = 30;
                cmdOk = true;
                break;
    
              case 9://init : close both shutters, bia_off, OK
                bia_mode = 0;
                cmdOk = true;
                break;

              case 10://error / command not found NOK
                break;
            }
            break;
    
          }
    
        case 30:// == BLUE Shutter OPEN & RED CLOSED
          {
            switch (command)
            {
              case 0://bia_on OK
                break;
    
              case 1://bia_off command while already off NOK
                break;
    
              case 2://shut_open : open both shutters OK
                bia_mode = 20;
                cmdOk = true;
                break;
    
              case 3://shut_close : close both shutters OK
                bia_mode = 0;
                cmdOk = true;
                break;
    
              case 4://reboot OK
                break;
    
              case 5://blue_open while blue shutter is already open NOK
                break;
    
              case 6://blue_close : close blue shutter only OK
                bia_mode = 0;
                cmdOk = true;
                break;
    
              case 7://red_open : open red shutter only OK
                bia_mode = 20;
                cmdOk = true;
                break;
    
              case 8://red_close while red shutter already closed NOK
                break;
    
              case 9://init, close both shutters, bia_off OK
                bia_mode = 0;
                cmdOk = true;
                break;

              case 10://error / command not found NOK
                break;
            }
            break;
          }
    
        case 40:// == RED Shutter OPEN & BLUE CLOSED
          {
            switch (command)
            {
              case 0://bia_on OK
                break;
    
              case 1://bia_off command while already off NOK
                break;
    
              case 2://shut_open : open both shutters OK
                bia_mode = 20;
                cmdOk = true;
                break;
    
              case 3://shut_close : close both shutters OK
                bia_mode = 0;
                cmdOk = true;
                break;
    
              case 4://reboot OK
                break;
    
              case 5://blue_open : open blue shutter only OK
                bia_mode = 20;
                cmdOk = true;
                break;
    
              case 6://blue_close while blue shutter is already closed NOK
                break;
    
              case 7://red_open while red shutter is already open NOK
                break;
    
              case 8://red_close : close red shutter only OK
                bia_mode = 0;
                cmdOk = true;
                break;
    
              case 9://init : close both shutters, bia_off OK
                bia_mode = 0;
                cmdOk = true;
                break;

              case 10://error / command not found NOK
                break;
            }
            break;
          }
      }
      if (!cmdOk){
        return cmdOk;
      }
    
      switch (bia_mode)
      { //Actions upon state
        case 0:  //All off.
          BIAIsOn = false;
    
          digitalWrite(g_pin, LOW);
    
          digitalWrite(7, LOW); //Both shutters closed
          digitalWrite(6, LOW);

//          ReportCompletion(STATUS_BCRC);
          if (!WaitForCompletion(STATUS_BCRC))
          {
            g_client.write("shutter switch timeout");
            cmdOk=false;
          }

          break;
    
        /////////////////////////////////////////////////////////////////// ACTIONS DU MODE 1 SHUTTER//
        case 10: //BIA is ON, shutters are closed
          BIAIsOn = true;
    
          digitalWrite(7, LOW);
          digitalWrite(6, LOW);
          
          if (!WaitForCompletion(STATUS_BCRC))
          {
            g_client.write("shutter switch timeout");
            cmdOk=false;
          }
          
          break;
        // //////////////////////////////////////////////////////////////////ACTIONS DU MODE BIA//
        case 20: //BIA is OFF, shutters are OPEN
    
          BIAIsOn = false;
          digitalWrite(g_pin, LOW);
    
          digitalWrite(7, HIGH);//OPEN
          digitalWrite(6, HIGH);//OPEN
          
          
          if (!WaitForCompletion(STATUS_BORO))
          {
            g_client.write("shutter switch timeout");
            cmdOk=false;
          }

          break;
    
        case 30:// BIA is OFF, Blue shutter is OPEN Red is CLOSED
          BIAIsOn = false;
          digitalWrite(g_pin, LOW);
    
          digitalWrite(7, HIGH); //OPEN
          digitalWrite(6, LOW);  //CLOSED
          
//          ReportCompletion(STATUS_BORC);
          if (!WaitForCompletion(STATUS_BORC))
          {
            g_client.write("shutter switch timeout");
            cmdOk=false;
          }

          break;
    
        case 40://BIA OFF, Red Shutter open, Blue closed
          BIAIsOn = false;
          digitalWrite(g_pin, LOW);
    
          digitalWrite(7, LOW); //CLOSED
          digitalWrite(6, HIGH);  //OPEN
          
//          ReportCompletion(STATUS_BCRO);
          if (!WaitForCompletion(STATUS_BCRO))
          {
            g_client.write("shutter switch timeout");
            cmdOk=false;
          }

          break;
      }
      return cmdOk;
    }
    
    
    bool CheckCommand(String command, String keyword)
    {
      int l = keyword.length();
      return (command.substring(0, l) == keyword);
    }
    
    void SetPeriod(int d)
    {
      //OCR1A = d;
    
      MsTimer2::stop();
      MsTimer2::set(d, Timer);
      MsTimer2::start();
    }
    
    int UpdateStatusWord()
    {
       ///// LECTURE EFFECTIVE DES STATUS SUR PORT IO ARDUINO //
      shb_open_status = digitalRead(3);       // BS ouvert//
      shb_close_status = digitalRead(4); // BS ferme //
      shb_err_status = digitalRead(2); // BS error //
      shr_open_status = digitalRead(8); // RS ouvert //
      shr_close_status = digitalRead(5);  // RS fermé //
      shr_err_status = digitalRead(1);  //RS error //

      StatWord = (1<<6)+
                 (!(shb_open_status)<<5)+
                 (!(shb_close_status)<<4)+
                 (!(shb_err_status)<<3)+
                 (!(shr_open_status)<<2)+
                 (!(shr_close_status)<<1)+
                 (!shr_err_status);
   
      return StatWord;
    }
    
    
    bool WaitForCompletion(int val)
    {
      int t, now;
      int v;
      
      t = millis();
      now = t;
      
      v = UpdateStatusWord();
      
      while ((v != val) && ((now-t)<ShutterMotionTimeout))
      {
        delay(10);
        v = UpdateStatusWord();
        now = millis();
      }
      
      return (v == val);
    }
    
  
    
    
    void Command(EthernetClient g_client, String mycommand)
    {
    
      UpdateStatusWord();
      
      int cmd = CommandCode(mycommand);

      bool cmdOk;
      cmdOk = StatusEvolve(cmd, g_client);
          
      // Controller status command parsing    
      
      if (CheckCommand(mycommand, "statword"))
      {
        g_client.print(StatWord);
        cmdOk = true;
      }
    
      if (CheckCommand(mycommand, "status"))
      {
        g_client.print(bia_mode);
        cmdOk = true;
      }
    
      if (CheckCommand(mycommand, "pulse_on"))
      {
        PulseMode = true;
        cmdOk = true;
      }
    
      if (CheckCommand(mycommand, "pulse_off"))
      {
        PulseMode = false;
        cmdOk = true;
      }
    
    
      ///////////////////////////////////// PROGRAMMATION DU TEMPS DE CYCLE TIMER PWM BIA /////////////////////////////////////////
      long v;
      if (CheckCommand(mycommand, "set_period"))
      {
        int mylen = mycommand.length() - 2;
        String inter = mycommand.substring(10, mylen);
    
        v = (long)inter.toInt();
        if ((v > 0) && (v < 65536)) {
          g_aperiod = v;
          SetPeriod(v);
        } //v is in ms
    
        Serial.println(g_aperiod);
        cmdOk = true;
      }
    
      if (CheckCommand(mycommand, "set_duty"))
      {
        int mylen = mycommand.length() - 2;
        String inter = mycommand.substring(8, mylen);
    
        v = inter.toInt();
        if ((v > 0) && (v < 256))
        {
          g_aduty = v;
        }
    
        Serial.println(g_aduty);
        cmdOk = true;
      }
    
      if (CheckCommand(mycommand, "get_period"))
      {
        g_client.print(g_aperiod);
        cmdOk = true;
      }
    
      if (CheckCommand(mycommand, "get_duty"))
      {
        g_client.print(g_aduty);
        cmdOk = true;
      }

      if (CheckCommand(mycommand, "get_param"))
      {
        g_client.print(PulseMode);
        g_client.print(',');
        g_client.print(g_aperiod);
        g_client.print(',');
        g_client.print(g_aduty);
        cmdOk= true;
      } 
      

      if (CheckCommand(mycommand, "set_timeout"))
      {
        int mylen = mycommand.length() - 2;
        String inter = mycommand.substring(10, mylen);
    
        v = (long)inter.toInt();
        if ((v > 0) && (v < 65536)) {
          ShutterMotionTimeout = v;
        } //v is in ms
        
        Serial.println(ShutterMotionTimeout);
        cmdOk = true;
      }
    
    
      ////////////////////////////////////////////////////////////////////////////////////////////////ARRET SERVEUR /////////////////////////////////////////////////////////////////////////
      if (CheckCommand(mycommand, "stop"))
      {
        bia_mode = 0;
        g_client.write("ok\r\n");
        g_client.stop();
        return ;
      }
    
      /////////////////////////////////////////////////////////////////////////////////////////////// AFFICHAGE COMMANDE NOK ///////////////////////////////////////////////////////////////////
      if (!cmdOk)
      {
        g_client.write("nok\r\n");
      }
      else
      {
        g_client.write("ok\r\n");
      }
    
        return;   
    }
    
    
    void software_reset() // Restarts program from beginning but does not reset the peripherals and registers
    {
      asm volatile ("  jmp 0");
    }
    
    ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    ///////////////////////////////////////////////////////////////////////////////////BOUCLE PRINCIPALE///////////////////////////////////////////////////////////////////////////////////////
    //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
    void loop() {
      //  Serial.println("Waiting...");
      EthernetClient g_client = g_server.available();
      if (g_client)
      {
        int taille = g_client.available();
    
        if (taille > 100)
          taille = 100;
    
        char data[taille + 1];
        int i = 0;
    
        while (i < taille)
        {
          char c = g_client.read();
          if (c !=  - 1)
          {
            data[i] = c;
            i++;
          }
        }
        data[i] = '\0';
        String mystring = (String)data;
        Command(g_client, mystring);
      }
    
      delay(10);
    }
