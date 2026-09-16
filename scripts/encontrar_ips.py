import speedtest

def detailed_speed_test():
    st = speedtest.Speedtest()
    
    # Get best server
    best_server = st.get_best_server()
    
    # Display server information
    print(f"Server: {best_server['sponsor']} ({best_server['name']})")
    print(f"Distance: {best_server['d']:.2f} km")
    print(f"Server IP: {best_server['ip']}")
    
    return {
        'server': best_server['sponsor'],
        'ip': best_server['ip']
    }

if __name__ == "__main__":
    result = detailed_speed_test()
    print(f"Best server: {result['server']}")