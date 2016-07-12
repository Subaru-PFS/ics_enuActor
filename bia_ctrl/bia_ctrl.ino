
#include <Stepper.h>

#include <Dhcp.h>
#include <Dns.h>
#include <Ethernet.h>
#include <EthernetClient.h>
#include <EthernetServer.h>
#include <EthernetUdp.h>
#include <util.h>

// LED diming board
// by Enos 2013/11/20

#include <SPI.h>
#include <Ethernet.h>
#include "TimerOne.h"

// Enter a MAC address and IP address for your controller below.
// The IP address will be dependent on your local network.
// gateway and subnet are optional:

byte mac[] = 
{
  0x90, 0xA2, 0xDA, 0x0F, 0xA0, 0x4F
};


// telnet defaults to port 23
EthernetServer g_server(23);
EthernetClient g_client;

// BIA Controller MODES
int bia_mode;
int safe_on;

int cmdnok;

int g_pin; // bia pin#
long g_aduty; // duty
long g_aperiod; // period

boolean shb_open_status;
boolean shb_close_status;
boolean shb_err_status;
boolean shr_open_status;
boolean shr_close_status;
boolean shr_err_status;



char statword [] ={"00000000"};

// setup
void setup()
{    
  Serial.begin(9600);
  // this check is only needed on the Leonardo:
   while (!Serial) {
    ; // wait for serial port to connect. Needed for Leonardo only
  }
  Serial.println("Search your Feelings");
  
  if (Ethernet.begin(mac) == 0) {
    Serial.println("Failed to configure Ethernet using DHCP");
    // no point in carrying on, so do nothing forevermore:
    for(;;);}
  Serial.println(Ethernet.localIP());
  g_server.begin();
  delay(1000);
 

   // Set BIA :ode to IDLE
  bia_mode = 0;
  safe_on = 0;
  
  //////////////////////////////////// PARAM BIA /////////////////////////////////////////
  g_aduty = 0; // 0% duty 
  g_aperiod = 100; // 100000 = 100ms 1000 = 1ms
  g_pin = 9;
   
  Timer1.initialize(300000); // the timer's period here (in microseconds)
  Timer1.pwm(9, 0); // setup pwm on pin 9, 0% duty cycle
  Timer1.setPwmDuty(9,0);
  
  //////////////////////////////////// PARAM SHUTTERS /////////////////////////////////////////
    // Config pin 7 en output (DF)
  pinMode(1,INPUT);
  pinMode(2,INPUT);
  pinMode(3,INPUT);
  pinMode(4,INPUT);
  pinMode(5,INPUT);
  pinMode(6,OUTPUT);
  pinMode(7,OUTPUT);
  pinMode(8,INPUT);

  
  g_client.read();
  g_client.flush();
   

}

void Command(EthernetClient g_client, String mycommand){

  cmdnok  = 2;
  
      ///// LECTURE EFFECTIVE DES STATUS SUR PORT IO ARDUINO //
  shb_open_status=digitalRead(8);         // BS ouvert//
  shb_close_status=digitalRead(5);   // BS ferme //
  shb_err_status=digitalRead(1); // BS error //
  shr_open_status=digitalRead(3);   // RS ouvert //
  shr_close_status=digitalRead(4);    // RS fermé //
  shr_err_status=digitalRead(2);    //RS error //


// MISE A JOUR DU MOT DE STATUS //
  if (shb_open_status == LOW){
    statword[0]='1'; }
  if (shb_open_status == HIGH){
    statword[0]='0'; }
      
  if (shb_close_status == LOW){
    statword[1]='1'; }
  if (shb_close_status == HIGH){
    statword[1]='0'; }
    
  if (shb_err_status == LOW){
    statword[2]='1';}
  if (shb_err_status == HIGH){
    statword[2]='0'; } 
     
  if (shr_open_status == LOW){
    statword[3]='1'; }
  if (shr_open_status == HIGH){
    statword[3]='0'; }
    
  if (shr_close_status == LOW){
    statword[4]='1'; }
  if (shr_close_status == HIGH){
    statword[4]='0'; } 
    
  if (shr_err_status == LOW){
    statword[5]='1'; }
  if (shr_err_status == HIGH){
    statword[5]='0'; }
    
  
  
    //////////////////////////////////// GESTION DU GRAFCET SANS LES ACTIONS /////////////////////////////////////////
  switch (bia_mode) {
    case 0:
    // We are in Idle state
      if (mycommand=="bia_on\r\n"){
          if (check_interlock(mycommand)==1){
            bia_mode = 2;
            cmdnok = 0;}
          else {
            g_client.write("intlk");
            cmdnok = 1;} 
      }
      
      if (mycommand=="shut_open\r\n"){
        if (check_interlock(mycommand)==1){
            bia_mode = 1;
            cmdnok = 0;}
          else {
          g_client.write("intlk");
          cmdnok = 1;}
      }  

      break;

    case 1:
    // We are in Shutter state
      if (mycommand=="shut_close\r\n"){
        bia_mode = 0;
        cmdnok = 0;}
    
      if (mycommand=="bia_on\r\n"){
        g_client.write("intlk"); 
        cmdnok  = 1;}
      break;

    case 2:
    // We are in BIA state
      if (mycommand=="bia_off\r\n"){
        bia_mode= 0;
        cmdnok = 0;}
    
      if (mycommand=="shut_open\r\n"){ 
        g_client.write("intlk");
        cmdnok = 1;}
      break;
    }
    //////////////////////////////////////////////// FIN EVOLUTION ETATS ///////////////////////////////////////////////////
    // Controller status command parsing
  
  
  if (mycommand=="init\r\n"){
    bia_mode = 0;
    cmdnok = 0;}
        
  if (mycommand=="statword\r\n"){
    g_client.write(statword); 
    g_client.write("\0");
    cmdnok = 1;}
    
  if (mycommand=="status\r\n"){ 
    g_client.print(bia_mode);
    cmdnok = 1;}
    


///////////////////////////////////// PROGRAMMATION DU TEMPS DE CYCLE TIMER PWM BIA /////////////////////////////////////////
  if (mycommand.substring(0,10)=="set_period"){
    int mylen=mycommand.length()-2;
    String inter=mycommand.substring(10,mylen);
    g_aperiod = (long)inter.toInt();
    Serial.println(g_aperiod);
    cmdnok = 0;} 
    
  if (mycommand.substring(0,8)=="set_duty"){
    int mylen=mycommand.length()-2;
    String inter=mycommand.substring(8,mylen);
    g_aduty=inter.toInt();
    Serial.println(g_aduty);
    cmdnok = 0;} 

  if (mycommand=="get_period\r\n"){
    g_client.print(g_aperiod);
    cmdnok = 1;} 
    
  if (mycommand=="get_duty\r\n"){
    g_client.print(g_aduty);
    cmdnok = 1;} 
    
  if (mycommand=="safe_on\r\n"){
    safe_on = 1;
    cmdnok = 1;}
    
  if (mycommand=="safe_off\r\n"){
    safe_on = 0;
    cmdnok = 1;}
    
   ////////////////////////////////////////////////////////////////////////////////////////////////ARRET SERVEUR /////////////////////////////////////////////////////////////////////////
  if (mycommand=="stop\r\n"){
    bia_mode = 0;
    g_client.write("ok\r\n");
    g_client.stop();
    return ;}
  
  /////////////////////////////////////////////////////////////////////////////////////////////// AFFICHAGE COMMANDE NOK ///////////////////////////////////////////////////////////////////
  if (cmdnok<2){
    g_client.write("ok\r\n");
  }
  else {
    g_client.write("nok\r\n");}
 
  if (cmdnok==1){
    return;}
  
    
///////////////////////////////////// ACTIONS FAITES SELON MODE ACTUEL BIA /////////////////////////////////////////////////////
  switch (bia_mode) {
    case 0:  ///////////////////////////////////ACTIONS FAITES PENDANT LE MODE 0 CAD IDLE: NI SHUTTER NI BIA//
      Timer1.setPwmDuty(g_pin, 0); // FORCAGE PWM BIA A ZERO 
      digitalWrite(7,LOW);          // FORCAGE FERMETURE SHUTTER B
      digitalWrite(6,LOW);          // FORCAGE FERMETURE SHUTTER R
      break;

/////////////////////////////////////////////////////////////////// ACTIONS DU MODE 1 SHUTTER//
    case 1:
      Timer1.setPwmDuty(g_pin, 0);  // FORCAGE BIA ETEINTE
       digitalWrite(7,HIGH);          // OUVERTURE SHUTTER B
       digitalWrite(6,HIGH);          // OUVERTURE SHUTTER R
      break;
    // //////////////////////////////////////////////////////////////////ACTIONS DU MODE BIA//
    case 2:
      Timer1.setPeriod(g_aperiod);        // DEMARRE LE TIMER PWM A LA PERIODE PROGRAMM
      Timer1.setPwmDuty(g_pin, g_aduty); // DEMARRE LE TIMER PWM AU TEMPS DE CYCLE PROGRAMME
      digitalWrite(7,LOW);               // FORCE FERMETURE SHUTTER B
      digitalWrite(6,LOW);               // FORCE FERMETURE SHUTTER R
      break;
  }

}

int check_interlock(String mycommand){
  if (safe_on==1){
    if (mycommand =="bia_on\r\n" && statword !="01001000") {return 0;}
    //if (mycommand =="shut_close\r\n" && statword !="01001000") {return 0;}     GET STATUS FROM PHOTODIODE
    }
  return 1;}
    
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////BOUCLE PRINCIPALE///////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

void loop() {
  EthernetClient g_client = g_server.available();
  if (g_client){
    int taille=g_client.available();
    char data[taille+1];
    int i=0;
    while (g_client.available()>0)
    {
      char c = g_client.read();
      if (c !=  - 1)
      {
       data[i]=c;
       i++;
        }
    }
    data[i]='\0';
    String mystring=(String)data;
    Command(g_client, mystring);
      
  }
 
}
